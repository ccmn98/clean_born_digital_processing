"""
file_format_scan_worker.py — integrated (self‑contained)

Drop this file into your project and remove the separate file_format_scan.py.
This module includes:
  • Siegfried scanning (sf.exe)
  • Results merge (scan_results.json)
  • Render data prep
  • HTML rendering (Jinja2)
  • PDF generation (wkhtmltopdf → WeasyPrint fallback) — preserves links
  • Excel (.xlsx) report with auto styling
  • CSV export
  • A dispatcher to create any combination of outputs
  • A PyQt5 QObject worker you can run in a QThread

Requires: jinja2, pandas, openpyxl, (optional) weasyprint, wkhtmltopdf (preferred for PDF)
"""

from __future__ import annotations

import os
import json
import shutil
import subprocess
import datetime as dt
import re
from pathlib import Path
from collections import Counter
from typing import Dict, List, Any, Optional, Callable

from jinja2 import Environment
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font
# PyQt worker base
from PyQt5.QtCore import QObject, pyqtSignal

# ──────────────────────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────────────────────

def _now_stamp() -> str:
    return dt.datetime.now().strftime('%m.%d.%Y_%I.%M%p').lower()


def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# Siegfried version check
# ──────────────────────────────────────────────────────────────────────────────


def get_siegfried_version(sf_path: str) -> str:
    try:
        proc = subprocess.run(
            [sf_path, "-version"],
            capture_output=True,
            text=True,
            check=True
        )
        # Expected: "siegfried 1.11.1"
        match = re.search(r"siegfried\s+([\d.]+)", proc.stdout)
        if match:
            return match.group(1)
        return proc.stdout.strip()
    except Exception as e:
        return f"unknown ({e})"

# ──────────────────────────────────────────────────────────────────────────────
# Siegfried helpers
# ──────────────────────────────────────────────────────────────────────────────

def _find_sf_executable() -> Optional[str]:
    """Return path to sf.exe (Siegfried) if found, else None.
    Checks local ./executables/sf.exe, PATH, and common Windows install paths.
    """
    exe = 'sf.exe' if os.name == 'nt' else 'sf'

    # 1) Local executables folder relative to this file
    here = Path(__file__).resolve().parent
    
    # 1) Executables next to this worker
    local1 = here / 'executables' / exe
    if local1.is_file():
        return str(local1)
    
    # 2) Executables in project core/executables
    local2 = here.parent / 'core' / 'executables' / exe
    if local2.is_file():
        return str(local2)

    # 3) PATH
    in_path = shutil.which(exe)
    if in_path:
        return in_path

    # 4) Common Windows paths
    candidates = [
        r"C:\\Program Files\\Siegfried\\" + exe,
        r"C:\\Program Files (x86)\\Siegfried\\" + exe,
    ]
    for c in candidates:
        if Path(c).is_file():
            return c

    return None


def _run_sf_on_file(file_path: str, sf_path: str) -> Dict[str, Any]:
    """Run siegfried on a single file and return parsed JSON block for that file.
    Adds convenience fields for creation/modified date/time if available.
    """
    # Use the executable directly; do not rely on PATH for full paths
    cmd = [sf_path, '-json', file_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', check=True)
    except subprocess.CalledProcessError as e:
        return {"file_name": os.path.basename(file_path), "filepath": file_path, "output": f"Error: {e}"}

    if not result.stdout:
        return {"file_name": os.path.basename(file_path), "filepath": file_path, "output": "No output from Siegfried."}

    try:
        block = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {"file_name": os.path.basename(file_path), "filepath": file_path, "output": f"Error decoding JSON: {e}"}

    block["file_name"] = os.path.basename(file_path)
    block["filepath"] = file_path

    # Normalize per-file results
    for f in block.get("files", []):
        # Extract first match summary fields
        f["matches_extracted"] = []
        for m in f.get("matches", []) or []:
            f["matches_extracted"].append({
                "id": m.get("id"),
                "format": m.get("format"),
                "version": m.get("version"),
                "mime": m.get("mime"),
            })

        # Normalize modified date/time if present
        mod = f.get("modified")
        if mod:
            try:
                modified_dt = dt.datetime.strptime(mod, "%Y-%m-%dT%H:%M:%S%z")
                f["modified_date"] = modified_dt.strftime("%m-%d-%Y")
                f["modified_time"] = modified_dt.strftime("%I:%M:%S %p")
            except Exception:
                pass

    block["details"] = block.get("identifiers", [{}])[0].get("details", "N/A")
    return block

def _normalize_inputs_map(inputs_map: dict) -> dict:
    """
    Accepts either:
      A) {digital_id: path}
      B) {path: digital_id}
    Returns:
      {digital_id: path}
    """
    if not inputs_map:
        return {}

    k, v = next(iter(inputs_map.items()))

    def looks_like_path(x) -> bool:
        s = str(x)
        return bool(re.match(r"^[A-Za-z]:", s)) or s.startswith(("\\\\", "/", "\\"))

    key_is_path = looks_like_path(k)
    val_is_path = looks_like_path(v)

    # If it looks like {path: digital_id}, flip it
    if key_is_path and not val_is_path:
        return {did: path for path, did in inputs_map.items()}

    # Otherwise assume already {digital_id: path}
    return dict(inputs_map)

def scan_drives_with_siegfried(
    inputs_map: Dict[str, str],
    progress_cb: Optional[Callable[[str], None]] = None
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    print(f"RESULTS: {results}")
    sf = _find_sf_executable()
    if not sf:
        raise RuntimeError("Siegfried (sf.exe) not found. Place sf.exe in ./executables or add to PATH.")

    # Normalize inputs so bare drive letters like 'D:' become 'D:\\'
    inputs_map = _normalize_inputs_map(inputs_map)
    norm_inputs: Dict[str, str] = {}
    print(f"NORM_INPUTS: {norm_inputs}")
    for did, p in (inputs_map or {}).items():
        p = os.path.abspath(p)
        if os.name == 'nt' and re.match(r'^[A-Za-z]:$', p):
            p += os.sep
        norm_inputs[did] = p
        
        if progress_cb:
            progress_cb(f"[filefmt] Using Siegfried at: {sf}")

    # print(f"[filefmt] Using Siegfried at: {sf}")
    # print(f"[filefmt] Inputs (raw): {inputs_map}")
    # print(f"[filefmt] Inputs (normalized): {norm_inputs}")

    # **Use normalized inputs here**
    for digital_id, drive in norm_inputs.items():
        if progress_cb:
            progress_cb(f"[{digital_id}] Scanning: {drive}")
        ok = os.path.isdir(drive)
        print(f"[filefmt] Will scan {drive} -> {digital_id} (isdir={ok})")
        if not ok:
            print(f"[filefmt] SKIP {drive}: not a directory -> {digital_id}")
            continue

        drive_file_results: List[Dict[str, Any]] = []
        start = dt.datetime.now()
        scan_date = start.strftime("%m-%d-%Y")
        scan_time = start.strftime("%I:%M:%S %p")

        for dirpath, _, filenames in os.walk(drive):
            for name in filenames:
                fp = os.path.abspath(os.path.join(dirpath, name))
                if not os.path.isfile(fp):
                    continue

                # (unchanged: creation_time code)
                try:
                    c_ts = os.path.getctime(fp)        # Windows: creation time; Unix: metadata change time
                except Exception:
                    c_ts = os.path.getmtime(fp)        # fallback

                c_dt = dt.datetime.fromtimestamp(c_ts)
                creation_date = c_dt.strftime("%m-%d-%Y")
                creation_time = c_dt.strftime("%I:%M:%S %p")


                block = _run_sf_on_file(fp, sf)
                for f in block.get('files', []) or []:
                    f['creation_date'] = creation_date
                    f['creation_time'] = creation_time
                drive_file_results.extend(block.get('files', []) or [])

        elapsed = (dt.datetime.now() - start).total_seconds()
        pretty = f"{elapsed:.2f} seconds" if elapsed < 120 else f"{int(elapsed // 60)}:{elapsed % 60:.2f} minutes"

        if progress_cb:
            progress_cb(f"✅ [{digital_id}] Scan complete: {drive} ({len(drive_file_results)} files, {pretty})")
        
        print(f"[filefmt] {digital_id} scanned {len(drive_file_results)} files in {pretty}")

        results.append({
            "digital_id": digital_id,
            "scan_date": scan_date,
            "scan_time": scan_time,
            "drive_time": pretty,
            "drive_letter": drive,
            "files": drive_file_results,
        })

    print(f"[filefmt] scan_drives_with_siegfried() -> "
          f"{sum(len(e['files']) for e in results)} files across {len(results)} inputs")
    return results


def merge_results_by_id(
    new_results: List[Dict[str, Any]],
    json_path: str | Path,
) -> Dict[str, Any]:
    json_path = Path(json_path)

    if json_path.exists():
        try:
            existing = json.loads(
                json_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            existing = {}
    else:
        existing = {}

    for entry in new_results:
        did = entry["digital_id"]
        existing[did] = entry

    json_path.write_text(
        json.dumps(existing, indent=2),
        encoding="utf-8",
    )

    return existing


# ──────────────────────────────────────────────────────────────────────────────
# Render data + templates
# ──────────────────────────────────────────────────────────────────────────────

def build_scan_metadata_lookup(
    inputs: Dict[str, str],
    selected_directories_dict: Dict[str, str],
    scan_results_path: str | Path,
) -> Dict[str, Any]:
    """
    Build report metadata using this priority:

        1. Current-run input data
        2. scan_results.json
        3. "N/A"
    """
    scan_results_path = Path(scan_results_path)

    if scan_results_path.exists():
        try:
            scan_results = json.loads(
                scan_results_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            scan_results = {}
    else:
        scan_results = {}

    normalized_inputs = _normalize_inputs_map(inputs or {})
    current_directories = dict(selected_directories_dict or {})

    media_ids = list(normalized_inputs)

    for digital_id in current_directories:
        if digital_id not in media_ids:
            media_ids.append(digital_id)

    for digital_id in scan_results:
        if digital_id not in media_ids:
            media_ids.append(digital_id)

    drive_lookup: Dict[str, str] = {}
    scan_date_lookup: Dict[str, str] = {}
    scan_time_lookup: Dict[str, str] = {}
    drive_time_lookup: Dict[str, str] = {}
    updated_inputs: List[Dict[str, str]] = []

    for digital_id in media_ids:
        saved_entry = scan_results.get(digital_id, {})

        current_path = (
            normalized_inputs.get(digital_id)
            or current_directories.get(digital_id)
        )

        saved_path = saved_entry.get("drive_letter")

        drive = current_path or saved_path or "N/A"

        drive_lookup[digital_id] = drive
        scan_date_lookup[digital_id] = (
            saved_entry.get("scan_date") or "N/A"
        )
        scan_time_lookup[digital_id] = (
            saved_entry.get("scan_time") or "N/A"
        )
        drive_time_lookup[digital_id] = (
            saved_entry.get("drive_time") or "N/A"
        )

        updated_inputs.append({
            "digital_id": digital_id,
            "path": drive,
        })

    return {
        "drive_lookup": drive_lookup,
        "scan_date_lookup": scan_date_lookup,
        "scan_time_lookup": scan_time_lookup,
        "drive_time_lookup": drive_time_lookup,
        "inputs": updated_inputs,
    }

def prepare_render_data(
    grouped_data: Dict[str, Any],
    drive_lookup: Dict[str, str],
    siegfried_version: str,
    base_output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    digital_media: Dict[str, List[Dict[str, Any]]] = {}
    scan_summary = Counter()

    # fill in any missing keys from grouped_data, but keep caller's mapping
    incoming_map = dict(drive_lookup or {})

    for did, entry in grouped_data.items():
        incoming_map.setdefault(
            did,
            entry.get("drive_letter", "N/A")
        )

    drive_lookup = incoming_map

    format_by_digital_id: Dict[str, Counter] = {}

    for digital_id, entry in grouped_data.items():

        enriched_files: List[Dict[str, Any]] = []
        fmt_counter: Counter = Counter()

        for f in entry.get('files', []) or []:
            # -------------------------------------------------------------
            # Normalize full_path and filename
            # -------------------------------------------------------------
            raw_name = f.get("filename", "") or f.get("file_name", "")

            # If raw_name looks like a path (drive letter or slash), treat it as full path
            if raw_name and (":" in raw_name or "\\" in raw_name or "/" in raw_name):
                full_path = raw_name
            else:
                full_path = f.get("filepath") or f.get("file_path") or ""

            f["file_path"] = full_path

            # Compute display filename (basename) from full_path if we have it
            if full_path:
                filename_only = Path(full_path).name
            else:
                filename_only = raw_name or "N/A"

            f["filename"] = filename_only

            # Optional debug (safe)
            # print(f"file path: {f['file_path']}")
            # print(f"file name: {f['filename']}")

            # -------------------------------------------------------------
            # Siegfried match fields
            # -------------------------------------------------------------
            if f.get('matches_extracted'):
                best = f['matches_extracted'][0]
                f['pronom_id'] = best.get('id', 'Unknown')
                f['format'] = best.get('format', 'Unknown')
                f['version'] = best.get('version', 'Unknown')
                f['mime_type'] = best.get('mime', 'Unknown')
            else:
                f['pronom_id'] = f.get('pronom_id', 'Unknown')
                f['format'] = f.get('format', 'Unknown')
                f['version'] = f.get('version', 'Unknown')
                f['mime_type'] = f.get('mime_type', 'Unknown')

            pid = f.get('pronom_id', 'Unknown')
            f['pronom_url'] = (
                f"https://www.nationalarchives.gov.uk/PRONOM/{pid}"
                if pid and str(pid).upper() != 'UNKNOWN'
                else ''
            )

            fmt_counter[(f['format'], f['pronom_id'], f['version'])] += 1
            scan_summary[(f['format'], f['pronom_id'], f['version'])] += 1
            enriched_files.append(f)

        digital_media[digital_id] = enriched_files
        format_by_digital_id[digital_id] = fmt_counter

    # overall scan summary
    summary_rows: List[Dict[str, Any]] = []
    for (fmt, pid, ver), count in scan_summary.most_common():
        summary_rows.append({
            'format_name': fmt,
            'format_id': pid,
            'version': ver,
            'counts': count,
        })

    data = {
        'title': 'File Analysis Results',
        'header': 'File Analysis Results',
        'description': 'This page contains the results of running sf.exe on each file in the specified directories.',
        'siegfried_version': siegfried_version,  # TODO: parse dynamically if desired
        'scan_summary': summary_rows,
        'digital_media': digital_media,
        'digital_format_summary': {},  # reserved
        'drive_lookup': drive_lookup,
        'show_unknown_formats': False,
        'show_duplicates': False,
    }

    # Optional debug dumps (safe, non-fatal)
# Optional debug dumps (written to user-selected output directory

    return data





def get_html_template() -> str:
    # (Template shortened to what you previously used; keep as-is.)
    return r"""
            <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>File Format Analysis Results: {{ title }}</title>
        <script>
        !function(){function r(t,e){if(!(this instanceof r))return new r(t,e);if(!t||"TABLE"!==t.tagName)throw new Error("Element must be a table");this.init(t,e||{})}function m(t){var e;return window.CustomEvent&&"function"==typeof window.CustomEvent?e=new CustomEvent(t):(e=document.createEvent("CustomEvent")).initCustomEvent(t,!1,!1,void 0),e}function p(t,e){return t.getAttribute(e.sortAttribute||"data-sort")||t.textContent||t.innerText||""}function v(t,e){return(t=t.trim().toLowerCase())===(e=e.trim().toLowerCase())?0:t<e?1:-1}function A(t,e){return[].slice.call(t).find(function(t){return t.getAttribute("data-sort-column-key")===e})}function E(n,o){return function(t,e){var r=n(t.td,e.td);return 0===r?o?e.index-t.index:t.index-e.index:r}}var x=[];r.extend=function(t,e,r){if("function"!=typeof e||"function"!=typeof r)throw new Error("Pattern and sort must be a function");x.push({name:t,pattern:e,sort:r})},r.prototype={init:function(t,e){var r,n,o,i=this;if(i.table=t,i.thead=!1,i.options=e,t.rows&&0<t.rows.length)if(t.tHead&&0<t.tHead.rows.length){for(a=0;a<t.tHead.rows.length;a++)if("thead"===t.tHead.rows[a].getAttribute("data-sort-method")){r=t.tHead.rows[a];break}r=r||t.tHead.rows[t.tHead.rows.length-1],i.thead=!0}else r=t.rows[0];if(r){function s(){i.current&&i.current!==this&&i.current.removeAttribute("aria-sort"),i.current=this,i.sortTable(this)}for(var a=0;a<r.cells.length;a++)(o=r.cells[a]).setAttribute("role","columnheader"),"none"!==o.getAttribute("data-sort-method")&&(o.tabindex=0,o.addEventListener("click",s,!1),null!==o.getAttribute("data-sort-default")&&(n=o));n&&(i.current=n,i.sortTable(n))}},sortTable:function(t,e){var r=this,n=t.getAttribute("data-sort-column-key"),o=t.cellIndex,i=v,s="",a=[],d=r.thead?0:1,u=t.getAttribute("data-sort-method"),l=t.getAttribute("aria-sort");if(r.table.dispatchEvent(m("beforeSort")),e||(l="ascending"===l||"descending"!==l&&r.options.descending?"descending":"ascending",t.setAttribute("aria-sort",l)),!(r.table.rows.length<2)){if(!u){for(;a.length<3&&d<r.table.tBodies[0].rows.length;)0<(s=(s=(f=n?A(r.table.tBodies[0].rows[d].cells,n):r.table.tBodies[0].rows[d].cells[o])?p(f,r.options):"").trim()).length&&a.push(s),d++;if(!a)return}for(d=0;d<x.length;d++)if(s=x[d],u){if(s.name===u){i=s.sort;break}}else if(a.every(s.pattern)){i=s.sort;break}for(r.col=o,d=0;d<r.table.tBodies.length;d++){var c,f,h=[],b={},w=0,g=0;if(!(r.table.tBodies[d].rows.length<2)){for(c=0;c<r.table.tBodies[d].rows.length;c++)"none"===(s=r.table.tBodies[d].rows[c]).getAttribute("data-sort-method")?b[w]=s:(f=n?A(s.cells,n):s.cells[r.col],h.push({tr:s,td:f?p(f,r.options):"",index:w})),w++;for("descending"===l?h.sort(E(i,!0)):(h.sort(E(i,!1)),h.reverse()),c=0;c<w;c++)b[c]?(s=b[c],g++):s=h[c-g].tr,r.table.tBodies[d].appendChild(s)}}r.table.dispatchEvent(m("afterSort"))}},refresh:function(){void 0!==this.current&&this.sortTable(this.current,!0)}},"undefined"!=typeof module&&module.exports?module.exports=r:window.Tablesort=r}();
        </script>
        
        <script>
            // Register numeric sorting before initializing the tables
            Tablesort.extend('number', function(item) {
                return /^[-+]?[0-9]*\.?[0-9]+$/.test(item.trim());
            }, function(a, b) {
                return parseFloat(a) - parseFloat(b);
            });

            // Register MM-DD-YYYY date sorting before initializing the tables
            Tablesort.extend('date', function(item) {
                return /^\d{2}-\d{2}-\d{4}$/.test(item.trim());
            }, function(a, b) {
                function parseDate(value) {
                    var parts = value.trim().split('-');

                    return new Date(
                        parseInt(parts[2], 10),
                        parseInt(parts[0], 10) - 1,
                        parseInt(parts[1], 10)
                    );
                }

                return parseDate(a) - parseDate(b);
            });

            // Initialize all sortable tables after the page loads
            document.addEventListener('DOMContentLoaded', function() {
                var sortableTables = document.querySelectorAll('table.sortable');

                sortableTables.forEach(function(table) {
                    new Tablesort(table);
                });
            });
        </script>

        <style>
            /* Recreating the navbar class */
            .navbar {
                position: fixed;
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.5rem 1rem;
                font-family: Arial, sans-serif;
                top: 0;
                width: 99%;
                z-index: 1000;

            }

            /* Recreating the navbar-expand-lg class */
            @media (min-width: 992px) {
                .navbar-expand-lg {
                    flex-wrap: nowrap;
                }
            }

            /* Recreating the navbar-dark class */
            .navbar-dark {
                color: #fff;
            }

            /* Recreating the bg-dark class */
            .bg-dark {
                background-color: #1963ad;
            }

            /* Additional styling for links in the navbar */
            .navbar a {
                color: #fff;
                text-decoration: none;
                margin: 0 10px;
            }

            .navbar a:hover {
                color: #ddd;
            }

            table {
            border-collapse: collapse;
            width: 100%;
            }

            th, td {
            padding: 3px;
            border: 1px solid black;
            }
            /* Make Scan Date / Scan Time columns wider and keep them on one line */
            .scan-information .digital-media-section table th:nth-child(3),
            .scan-information .digital-media-section table th:nth-child(4),
            .scan-information .digital-media-section table td:nth-child(3),
            .scan-information .digital-media-section table td:nth-child(4) {
                white-space: nowrap;
                min-width: 100px;
            }
            
            .scan-1{
                color: #003300;
                background-color:#F5F5DC;
            }
            .scan-2{
                color: #800000;
                background-color:#FFEBEB;
            }
            .scan-3{
                color: #000080;
                background-color:#FFFFE0;
            }
            .sortable {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                background-color: #f4f4f4;
            }
            .sortable th, .sortable td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
                white-space: normal;
                overflow-wrap: anywhere;
                word-break: break-word;

            }
            td.path, th.path {
                overflow-wrap: anywhere;
                word-break: break-all;      /* aggressive wrapping for paths */
}
            .sortable th {
                position: relative;
                cursor: pointer;
                padding-right: 24px;
            }

            .sortable th::after {
                content: "\2195";
                position: absolute;
                right: 6px;
                top: 50%;
                transform: translateY(-50%);
                color: #555;
            }

            .sortable th[aria-sort="ascending"]::after {
                content: "\2191";
            }

            .sortable th[aria-sort="descending"]::after {
                content: "\2193";
            }
            
            table.no-lines {
                border-collapse: collapse;
                width: 100%;
                border: 0;
            }
            .no-lines th, .no-lines td {
                border: 0;
                padding: 8px;
                /* Default horizontal alignment for all cells */
                vertical-align: middle; /* Default vertical alignment for all cells */
            }
            .no-lines th {
                text-align: center; /* Centers text in header cells */
                vertical-align: bottom; /* Aligns text to the bottom of the header cells */
                text-align: left;
            }
            .no-lines td {
                text-align: left; /* Right-aligns text in data cells */
            }
            p.float-left {
                float: left;
                margin-right: 10px; /* Adds space between the paragraphs */
            }
            /* Clearfix to solve the container not enclosing the floated elements */
            .clearfix::after {
                content: "";
                clear: both;
                display: table;
            }
            .duplicate-section, .unknown-section, .digital-media-section, .scan-summary-section, .scan-information, .scan-information {
                margin-bottom: 80px;
            }
            @media print {
                .sortable th, .sortable td { padding: 4px 5px; font-size: 11px; }
                .sortable th:nth-child(4),
                .sortable td:nth-child(4),
                .sortable th:nth-child(6),
                .sortable td:nth-child(6) { white-space: nowrap; }
        }
        /* Complete File Listing */

            .complete-listing-wrapper {
                width: 100%;
                overflow-x: auto;
                overflow-y: hidden;
                margin-top: 20px;
                border: 1px solid #ddd;
            }

            #sortable-complete {
                width: max-content;
                min-width: 100%;
                table-layout: auto;
                border-collapse: collapse;
                margin-top: 0;
            }

            #sortable-complete th,
            #sortable-complete td {
                padding: 8px 10px;
                vertical-align: top;
                text-align: left;
                word-break: normal;
                overflow-wrap: normal;
            }

            #sortable-complete th {
                white-space: nowrap;
                background-color: #e8eef5;
            }

            /* Filenames */
            #sortable-complete th:nth-child(2),
            #sortable-complete td:nth-child(2) {
                min-width: 180px;
                max-width: 320px;
                overflow-wrap: anywhere;
            }

            /* File paths */
            #sortable-complete th:nth-child(3),
            #sortable-complete td:nth-child(3) {
                min-width: 260px;
                max-width: 450px;
                overflow-wrap: anywhere;
            }

            /* Dates and times */
            #sortable-complete th:nth-child(5),
            #sortable-complete td:nth-child(5),
            #sortable-complete th:nth-child(6),
            #sortable-complete td:nth-child(6),
            #sortable-complete th:nth-child(7),
            #sortable-complete td:nth-child(7),
            #sortable-complete th:nth-child(8),
            #sortable-complete td:nth-child(8) {
                white-space: nowrap;
            }

            /* PRONOM identifiers */
            #sortable-complete th:nth-child(9),
            #sortable-complete td:nth-child(9) {
                white-space: nowrap;
            }

            /* Format and MIME type */
            #sortable-complete td:nth-child(10) {
                min-width: 180px;
                max-width: 260px;
                overflow-wrap: break-word;
            }

            #sortable-complete td:nth-child(12) {
                white-space: nowrap;
            }

            /* Alternating rows */
            #sortable-complete tbody tr:nth-child(even) {
                background-color: #f5f7fa;
            }

            #sortable-complete tbody tr:hover {
                background-color: #eaf2fb;
            }
        
        </style> 
    </head>
    <body id="Home" style="padding-top: 70px">
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
            <a class="navbar-brand" href="#">{{ title }}</a>
            <div class="collapse navbar-collapse" id="navbarNavAltMarkup">
                <div class="navbar-links">
                    <a href="#Home">Home</a>
                    <a href="#scan-information">Scan Information</a>
                    <a href="#scan-summary">Scan Summary</a>
                    <a href="#digital-media">Digital Media</a>
                    {% if show_unknown_formats %}
                        <a href="#unknown">Unknown File Formats</a>
                    {% endif %}
                    {% if show_duplicates %}
                        <a href="#">Duplicate files</a>
                    {% endif %}
                    <a href="#complete-listing">Complete file listing</a>
                </div>
            </div>
        </nav>
        <div class="container-fluid scan-information">
            {% if report_type == "PDF" %}
                <h1 style="text-align: center; margin-bottom: 40px;">File Format PDF Report</h1>
            {% else %}
                <h1 style="text-align: center; margin-bottom: 40px;">File Format HTML Report</h1>
            {% endif %}
            <h1>{{ header }}</h1>
            <p>{{ description }}</p>
            <h2>Inputs in This Report</h2>
                <ul>
                {% for inp in inputs %}
                    <li>{{ inp.digital_id }} → {{ inp.path }}</li>
                {% endfor %}
                </ul>
            <h2 id="scan-information">Scan Information:</h2>
            <div class="clearfix">
                <p class="float-left" style="font-weight:bold;">Siegfried Version</p>
                <p class="float-left" id="version-no">{{ siegfried_version }}</p>
            </div>
            <div class="digital-media-section">
                <table>
                    <thead>
                        <tr class="digital-media-id">
                            <th>Digital Media ID</th>
                            <th>Drive</th>
                            <th>Scan Date</th>
                            <th>Scan Time</th>
                            <th>Scan Time to Complete</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for media_id, files in digital_media.items() %}
                        <tr>
                            <td class="scan-{{ loop.index }}" id="{{ media_id }}_back">
                                <a href="#{{ media_id }}">{{ media_id }}</a>
                            </td>
                            <td class="scan-{{ loop.index }}">
                                {{ drive_lookup.get(media_id, 'N/A') }}
                            </td>
                            <td class="scan-{{ loop.index }}">
                                {{ scan_date_lookup.get(media_id, 'N/A') }}
                            </td>
                            <td class="scan-{{ loop.index }}">
                                {{ scan_time_lookup.get(media_id, 'N/A') }}
                            </td>
                            <td class="scan-{{ loop.index }}">
                                {{ drive_time_lookup.get(media_id, 'N/A') }}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="container-fluid scan-summary-section">
            <h2 id="scan-summary">Scan Summary:</h2>
            <h3 style="margin-left: 30px;">
                By PRONOM ID / File format
            </h3>

            <table class="sortable" id="sortable-summary">
                <thead>
                    <tr>
                        <th>Format Name</th>
                        <th>Pronom ID</th>
                        <th>Version</th>
                        <th data-sort-method="number">Counts</th>
                    </tr>
                </thead>

                <tbody>
                    {% for summary in scan_summary %}
                        <tr>
                            <td>{{ summary.format_name or "Unknown" }}</td>

                            {% if summary.format_id
                                and summary.format_id|string|upper != "UNKNOWN" %}
                                <td>
                                    <a
                                        href="https://www.nationalarchives.gov.uk/PRONOM/{{ summary.format_id }}"
                                        target="_blank"
                                    >
                                        {{ summary.format_id }}
                                    </a>
                                </td>
                            {% else %}
                                <td>UNKNOWN</td>
                            {% endif %}

                            <td>{{ summary.version or "" }}</td>
                            <td>{{ summary.counts }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>


            <div class="digital-media-section" id="digital-media">
                {% for media_id, files in digital_media.items() %}
                    <h2>Digital Media: {{ media_id }}</h2>

                    <h3 id="{{ media_id }}" style="margin-left: 20px;">
                        <a href="#{{ media_id }}_back">
                            {{ media_id }}
                        </a>
                    </h3>

                    <h4 style="margin-left: 40px;">File Results</h4>

                    <p style="margin-left: 40px;">
                        Drive: {{ drive_lookup.get(media_id, "N/A") }}
                    </p>

                    <table
                        class="sortable"
                        id="sortable-media-{{ loop.index }}"
                    >
                        <thead>
                            <tr>
                                <th>Filename</th>
                                <th>File path</th>
                                <th data-sort-method="number">Filesize</th>
                                <th data-sort-method="date">Creation Date</th>
                                <th>Creation Time</th>
                                <th data-sort-method="date">Modified Date</th>
                                <th>Modified Time</th>
                                <th>PRONOM ID</th>
                                <th>Format</th>
                                <th>Version</th>
                                <th>MIME Type</th>
                            </tr>
                        </thead>

                        <tbody>
                            {% for file in files %}
                                <tr>
                                    <td>{{ file.filename }}</td>

                                    <td class="path">
                                        {{ (file.file_path or file.filepath)
                                            | replace('\\', '\\<wbr>')
                                            | replace('/', '/<wbr>')
                                            | safe }}
                                    </td>

                                    <td>{{ file.filesize }}</td>
                                    <td>{{ file.creation_date }}</td>
                                    <td>{{ file.creation_time }}</td>
                                    <td>{{ file.modified_date }}</td>
                                    <td>{{ file.modified_time }}</td>

                                    <td>
                                        {% if file.pronom_url %}
                                            <a
                                                href="{{ file.pronom_url }}"
                                                target="_blank"
                                            >
                                                {{ file.pronom_id }}
                                            </a>
                                        {% else %}
                                            {{ file.pronom_id or "UNKNOWN" }}
                                        {% endif %}
                                    </td>

                                    <td>{{ file.format }}</td>
                                    <td>{{ file.version }}</td>
                                    <td>{{ file.mime_type }}</td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                {% endfor %}
            </div>
                        
            <div class="digital-media-section">
                <h2 id="complete-listing">Complete File Listing</h2>

                <div class="complete-listing-wrapper">
                    <table class="sortable" id="sortable-complete">
                    <thead>
                        <tr>
                            <th>Digital ID</th>
                            <th>Filename</th>
                            <th>File path</th>
                            <th data-sort-method="number">Filesize</th>
                            <th data-sort-method="date">Creation Date</th>
                            <th>Creation Time</th>
                            <th data-sort-method="date">Modified Date</th>
                            <th>Modified Time</th>
                            <th>PRONOM ID</th>
                            <th>Format</th>
                            <th>Version</th>
                            <th>MIME Type</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for media_id, files in digital_media.items() %}
                            {% for file in files %}
                                <tr>
                                    <td>{{ media_id }}</td>
                                    <td>{{ file.filename }}</td>
                                    <td class="path">{{ (file.file_path or file.filepath)
                                    | replace('\\', '\\<wbr>')
                                    | replace('/', '/<wbr>')
                                    | safe }}
                                    </td>
                                    <td>{{ file.filesize }}</td>
                                    <td>{{ file.creation_date }}</td>
                                    <td>{{ file.creation_time }}</td>
                                    <td>{{ file.modified_date }}</td>
                                    <td>{{ file.modified_time }}</td>
                                    <td>
                                        {% if file.pronom_url %}
                                            <a href="{{ file.pronom_url }}" target="_blank">
                                                {{ file.pronom_id }}
                                            </a>
                                        {% else %}
                                            {{ file.pronom_id or "UNKNOWN" }}
                                        {% endif %}
                                    </td>
                                    <td>{{ file.format }}</td>
                                    <td>{{ file.version }}</td>
                                    <td>{{ file.mime_type }}</td>
                                </tr>
                            {% endfor %}
                        {% endfor %}
                    </tbody>
                </table>
            </div> <!-- complete-listing-wrapper -->
        </div> <!-- digital-media-section -->
    </body>
    </html> """


# ──────────────────────────────────────────────────────────────────────────────
# HTML / PDF / Excel / CSV generators
# ──────────────────────────────────────────────────────────────────────────────

def render_html_report(data: Dict[str, Any], template_str: str, output_dir: Path | str) -> Path:
    env = Environment()
    template = env.from_string(template_str)
    output_html = template.render(**data)

    output_dir = Path(output_dir)
    _safe_mkdir(output_dir)
    out_path = output_dir / f"output_{_now_stamp()}.html"
    out_path.write_text(output_html, encoding='utf-8')
    return out_path


def _find_wkhtmltopdf() -> Optional[str]:
    """
    Locate wkhtmltopdf.exe from several known places.
    """

    # 0) Look in THIS project: core/executables/wkhtmltopdf/bin/
    project_embedded = Path(__file__).resolve().parent.parent/ "core" / "executables" / "wkhtmltopdf" / "bin" / "wkhtmltopdf.exe"

    if project_embedded.is_file():
        print(f"[filefmt] Using embedded wkhtmltopdf: {project_embedded}")
        return str(project_embedded)

    # 1) Explicit known system locations
    candidates = [
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
    ]
    for c in candidates:
        if Path(c).is_file():
            print(f"[filefmt] Using wkhtmltopdf at explicit path: {c}")
            return c

    # 2) PATH lookup
    exe = "wkhtmltopdf.exe" if os.name == "nt" else "wkhtmltopdf"
    in_path = shutil.which(exe)
    print(f"[filefmt] shutil.which({exe!r}) -> {in_path!r}")
    if in_path:
        return in_path

    print("[filefmt] wkhtmltopdf not found")
    return None

def _estimate_table_width_score(render_data: dict) -> dict:
    """Heuristically estimate how wide the Complete File Listing will be."""
    cols = 12  # Digital ID + 11 columns you render now
    total_chars = max_chars = n_cells = 0
    budget = 500
    for media_id, files in render_data.get("digital_media", {}).items():
        for f in files:
            if budget <= 0:
                break
            cells = [
                media_id,
                f.get("filename", ""),
                f.get("file_path") or f.get("filepath", ""),
                str(f.get("filesize", "")),
                f.get("creation_date", ""),
                f.get("creation_time", ""),
                f.get("modified_date", ""),
                f.get("modified_time", ""),
                f.get("pronom_id", ""),
                f.get("format", ""),
                f.get("version", ""),
                f.get("mime_type", ""),
            ]
            for c in cells:
                ln = len(str(c))
                total_chars += ln
                max_chars = max(max_chars, ln)
                n_cells += 1
            budget -= 1
        if budget <= 0:
            break
    avg_chars = (total_chars / n_cells) if n_cells else 0
    score = cols * 10 + avg_chars * 0.6 + max_chars * 0.8
    return {"cols": cols, "avg_chars": avg_chars, "max_chars": max_chars, "score": score}

def _pick_pdf_layout_for_score(score_info: dict) -> tuple[Optional[str], str, float, Optional[tuple[int, int]]]:
    s = score_info.get("score", 0)
    if s <= 120:  return ("Letter", "Portrait", 1.00, None)
    if s <= 160:  return ("Letter", "Landscape", 1.00, None)
    if s <= 210:  return ("Legal",  "Landscape", 0.95, None)
    if s <= 260:  return ("A3",     "Landscape", 0.90, None)
    # ultra-wide fallback
    return (None, "Landscape", 0.85, (500, 297))

def generate_pdf_report(
    html_file_path: Path | str,
    output_dir: Path | str,
    page_size: str | None = None,
    orientation: str | None = None,
    zoom: float | None = None,
    page_mm: tuple[int, int] | None = None,
) -> Path:
    html_file_path = Path(html_file_path)
    output_dir = Path(output_dir)
    _safe_mkdir(output_dir)

    pdf_out = output_dir / html_file_path.with_suffix('').name.replace('output_', 'report_')
    pdf_out = pdf_out.with_suffix('.pdf')

    wkhtml = _find_wkhtmltopdf()
    if not wkhtml:
        raise RuntimeError("wkhtmltopdf not installed or not found")

    cmd = [
        wkhtml,
            "--enable-local-file-access",
            "--load-error-handling", "ignore",
            "--margin-top", "12mm",
            "--margin-bottom", "12mm",
            "--margin-left", "7mm",          # was 10mm
            "--margin-right", "7mm",         # was 10mm
            "--viewport-size", "1920x1080",  # helps layout width
            "--dpi", "120",                  # slightly denser CSS pixels → more content fits
            "--minimum-font-size", "8",
    ]
    if page_mm:
        w, h = page_mm
        cmd += ["--page-width",  f"{w}mm", "--page-height", f"{h}mm"]
    elif page_size:
        cmd += ["--page-size", page_size]
    if orientation:
        cmd += ["--orientation", orientation]
    if zoom and abs(zoom - 1.0) > 1e-6:
        cmd += ["--zoom", f"{zoom:.2f}"]

    cmd += [str(html_file_path), str(pdf_out)]
    print(f"[filefmt] Running wkhtmltopdf: {' '.join(cmd)}")

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(
            f"wkhtmltopdf failed with exit code {result.returncode}\n"
            f"stderr:\n{result.stderr.decode('utf-8', errors='ignore')}"
        )

    print(f"[filefmt] PDF created: {pdf_out}")
    return pdf_out


def generate_excel_report(output_dir: Path | str, data: Dict[str, Any]) -> Path:
    output_dir = Path(output_dir)
    _safe_mkdir(output_dir)

    xlsx_path = output_dir / f"file_format_analysis{_now_stamp()}.xlsx"

    with pd.ExcelWriter(xlsx_path, engine='openpyxl', mode='w') as writer:
        # Header sheet: Scan Summary
        header = pd.DataFrame({
            'Field': ['Siegfried Version', 'Project Title', 'Generated On'],
            'Value': [
                data.get('siegfried_version', 'N/A'),
                data.get('title', 'N/A'),
                dt.datetime.now().strftime('%m-%d-%Y %I:%M %p'),
            ]
        })
        sheet = 'Scan Summary'
        header.to_excel(writer, sheet_name=sheet, startrow=0, index=False)

        df_summary = pd.DataFrame(data.get('scan_summary', []))
        df_summary.to_excel(writer, sheet_name=sheet, startrow=len(header) + 3, index=False)

        # Per-digital ID sheets
        for media_id, files in data.get('digital_media', {}).items():
            rows = []
            for f in files:
                rows.append({
                    'Filename': Path(f.get('filename', '')).name if f.get('filename') else 'N/A',
                    'Filepath': f.get('file_path') or f.get('filename', 'N/A'),
                    'Filesize (bytes)': f.get('filesize', 'N/A'),
                    'Modified Date': f.get('modified_date', 'N/A'),
                    'Modified Time': f.get('modified_time', 'N/A'),
                    'Pronom ID': f.get('pronom_id', 'Unknown'),
                    'Format': f.get('format', 'Unknown'),
                    'Version': f.get('version', 'Unknown'),
                    'Mime Type': f.get('mime_type', 'Unknown'),
                })
            pd.DataFrame(rows).to_excel(writer, sheet_name=media_id[:31], index=False)

        # Complete listing
        all_rows = []
        for media_id, files in data.get('digital_media', {}).items():
            for f in files:
                all_rows.append({
                    'Digital ID': media_id,
                    'Filename': Path(f.get('filename', '')).name if f.get('filename') else 'N/A',
                    'Filepath': f.get('file_path') or f.get('filename', 'N/A'),
                    'Filesize (bytes)': f.get('filesize', 'N/A'),
                    'Modified Date': f.get('modified_date', 'N/A'),
                    'Modified Time': f.get('modified_time', 'N/A'),
                    'Pronom ID': f.get('pronom_id', 'Unknown'),
                    'Format': f.get('format', 'Unknown'),
                    'Version': f.get('version', 'Unknown'),
                    'Mime Type': f.get('mime_type', 'Unknown'),
                })
        pd.DataFrame(all_rows).to_excel(writer, sheet_name='Complete File Listing', index=False)

    _auto_style_excel(xlsx_path)
    return xlsx_path


def _auto_style_excel(excel_path: Path) -> None:
    wb = load_workbook(excel_path)

    # ---------------------------------------------------------
    # Scan Summary formatting
    # ---------------------------------------------------------
    if 'Scan Summary' in wb.sheetnames:
        ws = wb['Scan Summary']

        # Bold first two rows
        for row in ws.iter_rows(min_row=1, max_row=2):
            for cell in row:
                cell.font = Font(bold=True)

        # Bold header of summary table
        start_table_row = 6
        for cell in ws[start_table_row]:
            cell.font = Font(bold=True)

    # ---------------------------------------------------------
    # Add PRONOM hyperlinks to every worksheet
    # ---------------------------------------------------------
    for ws in wb.worksheets:

        pronom_columns = []

        # Find any column whose header is "Pronom ID"
        for row in ws.iter_rows():
            for cell in row:
                if (
                    isinstance(cell.value, str)
                    and cell.value.strip().lower() == "pronom id"
                ):
                    pronom_columns.append(
                        (cell.column, cell.row)
                    )

        # Add hyperlinks below each PRONOM ID header
        for column_number, header_row in pronom_columns:

            for row_number in range(
                header_row + 1,
                ws.max_row + 1
            ):
                cell = ws.cell(
                    row=row_number,
                    column=column_number
                )

                pronom_id = cell.value

                if (
                    pronom_id
                    and str(pronom_id).strip()
                    and str(pronom_id).upper() != "UNKNOWN"
                    and str(pronom_id).upper() != "N/A"
                ):
                    cell.hyperlink = (
                        "https://www.nationalarchives.gov.uk/"
                        f"PRONOM/{pronom_id}"
                    )

                    # Make it look like a normal Excel hyperlink
                    cell.style = "Hyperlink"

        # -----------------------------------------------------
        # Autofit columns
        # -----------------------------------------------------
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter

            for cell in col:
                try:
                    if cell.value is not None:
                        max_len = max(
                            max_len,
                            len(str(cell.value))
                        )
                except Exception:
                    pass

            ws.column_dimensions[col_letter].width = min(
                max_len + 2,
                75
            )

    wb.save(excel_path)


def generate_csv_report(output_dir: Path | str, data: Dict[str, Any]) -> Path:
    import csv
    output_dir = Path(output_dir)
    _safe_mkdir(output_dir)
    csv_path = output_dir / f"file_format_analysis_{_now_stamp()}.csv"

    rows: List[Dict[str, Any]] = []
    for media_id, files in data.get('digital_media', {}).items():
        for f in files:
            rows.append({
                'Digital ID': media_id,
                'Filename': f.get('filename', ''),
                'Filepath': f.get('file_path') or f.get('filepath', ''),
                'Filesize': f.get('filesize', ''),
                'Creation Date': f.get('creation_date', ''),
                'Creation Time': f.get('creation_time', ''),
                'Modified Date': f.get('modified_date', ''),
                'Modified Time': f.get('modified_time', ''),
                'PRONOM ID': f.get('pronom_id', ''),
                'Format': f.get('format', ''),
                'Version': f.get('version', ''),
                'MIME Type': f.get('mime_type', ''),
            })

    fieldnames = list(rows[0].keys()) if rows else [
        'Digital ID','Filename','Filepath','Filesize','Creation Date','Creation Time',
        'Modified Date','Modified Time','PRONOM ID','Format','Version','MIME Type'
    ]

    with open(csv_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def run_outputs(
    render_data: Dict[str, Any],
    html_template: str,
    output_dir: Path | str,
    do_html: bool,
    do_pdf: bool,
    do_excel: bool,
    do_csv: bool,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, str]:
    
    output_dir = Path(output_dir)
    
    _safe_mkdir(output_dir)

    created: Dict[str, str] = {}

    # ---------------------------------------------------------
    # HTML output
    # ---------------------------------------------------------
    if do_html:
        if progress_callback:
            progress_callback(
                "Generating HTML report..."
            )

        data_for_html = dict(render_data)
        data_for_html["report_type"] = "HTML"

        html_path = render_html_report(
            data_for_html,
            html_template,
            output_dir
        )

        created["html"] = str(html_path)

        if progress_callback:
            progress_callback(
                "HTML report created."
            )

    
    # ---------------------------------------------------------
    # PDF output
    # ---------------------------------------------------------
    if do_pdf:
        if progress_callback:
            progress_callback(
                "Generating PDF report..."
            )

        data_for_pdf = dict(render_data)
        data_for_pdf["report_type"] = "PDF"

        pdf_temp_dir = output_dir / "pdf_tmp"

        pdf_html_path = render_html_report(
            data_for_pdf,
            html_template,
            pdf_temp_dir
        )

        score_info = _estimate_table_width_score(
            render_data
        )

        page_size, orientation, zoom, page_mm = (
            _pick_pdf_layout_for_score(score_info)
        )

        pdf_path = generate_pdf_report(
            pdf_html_path,
            output_dir,
            page_size=page_size,
            orientation=orientation,
            zoom=zoom,
            page_mm=page_mm,
        )

        created["pdf"] = str(pdf_path)

        try:
            pdf_html_path.unlink(missing_ok=True)
            pdf_temp_dir.rmdir()
        except Exception:
            pass

        if progress_callback:
            progress_callback(
                "PDF report created."
            )

    # ---------------------------------------------------------
    # Excel output
    # ---------------------------------------------------------
    if do_excel:
        if progress_callback:
            progress_callback(
                "Generating Excel report..."
            )

        xlsx_path = generate_excel_report(
            output_dir,
            render_data
        )

        created["excel"] = str(xlsx_path)

        if progress_callback:
            progress_callback(
                "Excel report created."
            )

    # ---------------------------------------------------------
    # CSV output
    # ---------------------------------------------------------
    if do_csv:
        if progress_callback:
            progress_callback(
                "Generating CSV report..."
            )

        csv_path = generate_csv_report(
            output_dir,
            render_data
        )

        created["csv"] = str(csv_path)

        if progress_callback:
            progress_callback(
                "CSV report created."
            )

    return created



# ──────────────────────────────────────────────────────────────────────────────
# PyQt Worker
# ──────────────────────────────────────────────────────────────────────────────
class FileFormatScanWorker(QObject):
    """
    Scan inputs with Siegfried and generate requested outputs.

    base_output_dir: root folder (we will create base_output_dir/"reports")
    inputs_map: dict of digital_id -> path (drive or directory)
    bagger_info: optional dict; will be added to render_data as 'bagger_info'
    do_html/do_pdf/do_csv/do_excel: booleans from UI checkboxes
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)   # { 'html': path, 'pdf': path, 'csv': path, 'excel': path }
    error = pyqtSignal(str)
    reports_ready = pyqtSignal(str, dict)  # digital_id, {"html": "...", "pdf": "...", "excel": "..."}
    
    def __init__(
        self,
        base_output_dir: str | Path,
        inputs_map: Dict[str, str],
        bagger_info: Optional[Dict[str, str]] = None,
        do_html: bool = False,
        do_pdf: bool = False,
        do_csv: bool = False,
        do_excel: bool = False,
    ) -> None:
        super().__init__()
        self.base_output_dir = Path(base_output_dir)
        self.inputs_map = dict(inputs_map or {})
        self.bagger_info = dict(bagger_info or {})
        self.do_html = bool(do_html)
        self.do_pdf = bool(do_pdf)
        self.do_csv = bool(do_csv)
        self.do_excel = bool(do_excel)

    def run(self) -> None:
        try:
            msg = (
                f"Output options: HTML={self.do_html}, PDF={self.do_pdf}, "
                f"Excel={self.do_excel}, CSV={self.do_csv}"
            )
            self.progress.emit(msg)
            print(msg)  # <- goes to terminal / VS Code Output

            self.progress.emit('Starting file format scan…')

            reports_dir = self.base_output_dir / 'reports'
            _safe_mkdir(reports_dir)
            
            # * * Getting the Siegfried version * *
            sf = _find_sf_executable()
            if not sf:
                raise RuntimeError("Siegfried (sf.exe) not found")

            self.sf_version = get_siegfried_version(sf)
            self.progress.emit(f"Siegfried version: {self.sf_version}")
            

            # 1) Scan
            self.progress.emit('Scanning files with Siegfried…')
            results = scan_drives_with_siegfried(self.inputs_map, progress_cb=self.progress.emit)
            #print(f"File foramt scan worker-line_720: {results}")

            # 2) Merge
            self.progress.emit('Merging results…')
            
            temp_dir = self.base_output_dir / 'temp_files'
            temp_dir.mkdir(parents=True, exist_ok=True)

            json_path = temp_dir / 'scan_results.json'
            grouped = merge_results_by_id(results, json_path)
            

            # 3) Prepare render data
            self.progress.emit('Preparing render data…')
            
            metadata = build_scan_metadata_lookup(
                self.inputs_map,
                self.inputs_map,
                json_path,
            )
            render_data = prepare_render_data(grouped, metadata["drive_lookup"], self.sf_version, self.base_output_dir)
            
            render_data.update(metadata)

            if self.bagger_info:
                render_data['bagger_info'] = self.bagger_info

            # 4) Outputs
            self.progress.emit('Generating outputs…')
            created = run_outputs(
                render_data,
                get_html_template(),
                reports_dir,
                do_html=self.do_html,
                do_pdf=self.do_pdf,
                do_excel=self.do_excel,
                do_csv=self.do_csv,
                progress_callback=self.progress.emit,
            )

            self.finished.emit(created)
        except Exception as e:
            self.error.emit(str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Optional CLI test (helps verify outside the GUI)
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run an ad-hoc Siegfried scan and generate reports.')
    parser.add_argument('--out', required=True, help='Base output directory (reports/ will be created inside)')
    parser.add_argument('--id', action='append', nargs=2, metavar=('DIGITAL_ID', 'PATH'), help='Map a digital_id to a path; can be used multiple times')
    parser.add_argument('--html', action='store_true')
    parser.add_argument('--pdf', action='store_true')
    parser.add_argument('--csv', action='store_true')
    parser.add_argument('--excel', action='store_true')
    args = parser.parse_args()

    base = Path(args.out)
    _safe_mkdir(base)
    inputs = {did: p for (did, p) in (args.id or [])}

    # Minimal non-Qt path for quick testing
    print('Scanning…')
    res = scan_drives_with_siegfried(inputs)
    sf_path = _find_sf_executable()
    
    sf_version = (
        get_siegfried_version(sf_path)
        if sf_path
        else "unknown"
    )
    
        
    # Make sure temp_files exists
    temp_dir = base / 'temp_files'
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Save / read scan_results.json from temp_files

    json_path = temp_dir / 'scan_results.json'
    grouped = merge_results_by_id(res, json_path)

    metadata = build_scan_metadata_lookup(
        inputs,
        inputs,
        json_path,
    )

    data = prepare_render_data(
        grouped,
        metadata["drive_lookup"],
        sf_version,
        base,
    )

    data.update(metadata)
    
    created = run_outputs(
        data,
        get_html_template(),
        base / "reports",
        args.html,
        args.pdf,
        args.excel,
        args.csv,
        progress_callback=print,
    )
    print('Created:', created)

