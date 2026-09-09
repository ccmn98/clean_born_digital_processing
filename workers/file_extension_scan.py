import os
import csv
import pandas as pd
from pathlib import Path
from PyQt5.QtCore import pyqtSignal, QThread
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
import re
from core.config import TEMP_DIR

# ===================================
# Configuration & constants
# ===================================


# Temp directory for intermediate CSVs
FILE_EXTENSION_TEMP_DIR = TEMP_DIR / "file_extension_scan"
FILE_EXTENSION_TEMP_DIR.mkdir(parents=True, exist_ok=True)

BASE_FILENAME = "file_extension_scan_report"
MAX_FILE_SIZE_MB = 10  # Max Excel file size before creating a new report

# Define file extension categories
compressed_files_ext = ['.zip', '.rar', '.tar', '.gz', '.bz2', '.7z', '.xz', '.lz', '.z', '.arj', '.lzh', '.tgz', '.tbz2', '.txz', '.zst', '.sit']
email_files_ext = ['.pst', '.eml', '.msg', '.mbox', '.ost', '.olm', '.dbx', '.mbx', '.mime', '.nws', '.vcf', '.ics']
multimedia_files_ext = ['.vob', '.cda']
apple_patterns = ['._', '.DS_Store', '.AppleDouble']

# Combine all extensions into a single list
combined_extensions = compressed_files_ext + email_files_ext + multimedia_files_ext + apple_patterns


class FileExtensionScanWorker(QThread):
    progress_signal = pyqtSignal(str)   # Signal for progress messages
    completed_signal = pyqtSignal(dict) # Signal to send results back

    def __init__(self, input_dict, output_directory, task_type="directory"):
        super().__init__()
        self.input_dict = input_dict
        self.output_directory = output_directory
        self.task_type = task_type
        
        self.reports_output_dir = Path(self.output_directory) / "reports"
        self.reports_output_dir.mkdir(parents=True, exist_ok=True)

        print(
            "def__init__--FileExtensionScanWorker:\n"
            f"self.input_dict: {self.input_dict}\n"
            f"self.output_directory: {self.output_directory}\n"
            f"self.task_type: {self.task_type}"
        )

    # Get file size in MB
    def get_excel_file_size(self, file_path):
        return os.path.getsize(file_path) / (1024 * 1024) if os.path.exists(file_path) else 0

    # -----------------------------------
    # Scan directories and write temp CSVs
    # -----------------------------------
    def scan_directories(self):
        temp_files = []
        file_index = 1

        reports_output_dir = Path(self.output_directory) / "reports"
        reports_output_dir.mkdir(parents=True, exist_ok=True)

        # Open first temp file (keep handle so we can roll safely)
        current_file_name = TEMP_DIR / f"temp_data_{file_index}.csv"
        csv_file = current_file_name.open("w", newline="", encoding="utf-8")
        writer = csv.writer(csv_file)
        writer.writerow(["Digital ID", "File Extension", "File Path", "File Size (MB)"])

        try:
            for digID, directory_drive in self.input_dict.items():
                print(
                    f"Input dict: {self.input_dict}\n"
                    f"Directory Drive: {directory_drive}\n"
                    f"Digital ID: {digID}"
                )
                digital_id_entries = []  # Buffer entries for this Digital ID

                if self.task_type == "drive" and not os.path.ismount(directory_drive):
                    self.progress_signal.emit(f"Not a valid drive: {directory_drive}")
                    continue
                elif self.task_type == "directory" and not os.path.isdir(directory_drive):
                    self.progress_signal.emit(f"Not a valid directory: {directory_drive}")
                    continue

                for root, _, files in os.walk(directory_drive):
                    for file in files:
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in combined_extensions:
                            file_path = os.path.join(root, file)
                            file_size = self.get_excel_file_size(file_path)
                            formatted_file_size = f"{file_size:.3f}"
                            digital_id_entries.append([digID, file_ext, file_path, formatted_file_size])

                # Estimate size impact of adding this block
                estimated_size = sum(
                    len(",".join(map(str, row))) for row in digital_id_entries
                ) / (1024 * 1024)

                # Roll to a new file if needed
                if self.get_excel_file_size(str(current_file_name)) + estimated_size > MAX_FILE_SIZE_MB:
                    # Close current, remember it, and open the next
                    csv_file.close()
                    temp_files.append(str(current_file_name))
                    file_index += 1
                    current_file_name = TEMP_DIR / f"temp_data_{file_index}.csv"
                    csv_file = current_file_name.open("w", newline="", encoding="utf-8")
                    writer = csv.writer(csv_file)
                    writer.writerow(["Digital ID", "File Extension", "File Path", "File Size (MB)"])

                # Write this Digital ID's rows
                if digital_id_entries:
                    writer.writerows(digital_id_entries)

        finally:
            # Always close the currently open temp file and record it
            csv_file.close()
            temp_files.append(str(current_file_name))

        return temp_files

    # -----------------------------------
    # Thread run
    # -----------------------------------
    def run(self):
        try:
            self.progress_signal.emit("Scanning files...")
            temp_files = self.scan_directories()

            self.progress_signal.emit("Compiling Excel reports...")
            self.compile_to_excel(temp_files)

            self.progress_signal.emit("Cleaning up temporary files...")
            self.cleanup_temp_csvs(temp_files)

            self.completed_signal.emit({"Status": "Success"})
        except Exception as e:
            self.progress_signal.emit(f"Error during scan: {str(e)}")
            self.completed_signal.emit({"status": "error", "message": str(e)})

    # -----------------------------------
    # Compile temp CSVs -> formatted Excel
    # -----------------------------------
    def compile_to_excel(self, temp_files):
        file_index = 1
        file_name = Path(self.output_directory) / (self.reports_output_dir)/f"{BASE_FILENAME}_{file_index}.xlsx"

        summary_data = []
        digital_id_data = {}

        # File Category Mapping
        category_map = {
            **{ext: "Compressed Files" for ext in compressed_files_ext},
            **{ext: "Email Files" for ext in email_files_ext},
            **{ext: "Multimedia Files" for ext in multimedia_files_ext},
            **{ext: "Apple Patterns" for ext in apple_patterns},
        }

        for csv_file in temp_files:
            # Normalize any accidental bare/absolute names
            p = Path(str(csv_file))
            if not p.is_absolute():
                p = TEMP_DIR / p.name.lstrip("/\\")  # Keep inside TEMP_DIR

            df = pd.read_csv(p)

            # Group by Digital ID and File Extension, count occurrences
            grouped = df.groupby(["Digital ID", "File Extension"]).size().reset_index(name="Total Files")

            for _, row in grouped.iterrows():
                digID = row["Digital ID"]
                ext = row["File Extension"]
                total_files = row["Total Files"]
                file_category = category_map.get(ext, "Unknown")
                summary_data.append([digID, ext, file_category, total_files])

            # Store per-Digital ID details for their respective sheets
            for _, row in df.iterrows():
                digID = row["Digital ID"]
                ext = row["File Extension"]
                file_path = row["File Path"]
                file_size = row["File Size (MB)"]

                if digID not in digital_id_data:
                    digital_id_data[digID] = []
                digital_id_data[digID].append([ext, file_path, file_size])

            # Save and check if file size exceeded MAX_FILE_SIZE_MB
            self.save_excel(str(file_name), summary_data, digital_id_data)

            if self.get_excel_file_size(str(file_name)) > MAX_FILE_SIZE_MB:
                file_index += 1
                file_name = Path(self.output_directory) / (self.reports_output_dir)/f"{BASE_FILENAME}_{file_index}.xlsx"
                summary_data = []
                digital_id_data = {}

    # -----------------------------------
    # Save Excel and apply formatting
    # -----------------------------------
    def save_excel(self, file_name, summary_data, digital_id_data):
        with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
            # Summary sheet
            summary_df = pd.DataFrame(
                summary_data,
                columns=["Digital ID", "File Extension", "File Category", "Total Files"]
            )
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

            # Section headers per sheet
            section_headers = {
                "Compressed Files": compressed_files_ext,
                "Email Files": email_files_ext,
                "Multimedia Files": multimedia_files_ext,
                "Apple Patterns": apple_patterns,
            }

            # Per-Digital ID sheets with grouped extensions
            for digID, rows in digital_id_data.items():
                grouped_data = []
                sorted_rows = sorted(rows, key=lambda x: x[0])  # sort by extension

                for category, extensions in section_headers.items():
                    category_files = [row for row in sorted_rows if row[0] in extensions]
                    if category_files:
                        grouped_data.append([category, "", ""])  # section header row
                        grouped_data.extend(category_files)

                df = pd.DataFrame(grouped_data, columns=["File Extension", "File Path", "File Size (MB)"])
                df.to_excel(writer, sheet_name=digID, index=False)

        # Post-formatting & hyperlinks
        self.apply_excel_formatting(file_name, digital_id_data)

    # -----------------------------------
    # Formatting and hyperlinks
    # -----------------------------------
    def apply_excel_formatting(self, file_name, digital_id_data):
        wb = load_workbook(file_name)

        # Colors for groups and their data rows
        color_map = {
            "Compressed Files": "FFC000",  # Orange
            "Email Files": "92D050",       # Green
            "Multimedia Files": "4F81BD",  # Blue
            "Apple Patterns": "A9A9A9",    # Gray
        }
        lighter_color_map = {
            "Compressed Files": "FFE699",  # Light Yellow
            "Email Files": "C6E0B4",       # Light Green
            "Multimedia Files": "D6EAF8",  # Light Blue
            "Apple Patterns": "E5E5E5",    # Light Gray
        }

        thin_border = Border(left=Side(style="thin"), right=Side(style="thin"),
                             top=Side(style="thin"), bottom=Side(style="thin"))
        thick_border = Border(left=Side(style="medium"), right=Side(style="medium"),
                              top=Side(style="medium"), bottom=Side(style="medium"))

        # Summary formatting
        if "Summary" in wb.sheetnames:
            ws_summary = wb["Summary"]

            # Borders for data rows
            for row in ws_summary.iter_rows(min_row=2, max_row=ws_summary.max_row,
                                            min_col=1, max_col=ws_summary.max_column):
                for cell in row:
                    cell.border = thin_border

            # Header style
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            for cell in ws_summary[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.border = thick_border

        # Per-Digital ID formatting
        for sheet_name in wb.sheetnames:
            if sheet_name == "Summary":
                continue
            ws = wb[sheet_name]

            # Headers
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
                cell.border = thick_border

            # Borders for all data cells
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row,
                                    min_col=1, max_col=ws.max_column):
                for cell in row:
                    cell.border = thin_border

            # Color bands per section
            current_group_color = None
            current_data_color = None
            for row in range(2, ws.max_row + 1):
                cell_value = ws[f"A{row}"].value
                if cell_value in color_map:
                    current_group_color = color_map[cell_value]
                    current_data_color = lighter_color_map[cell_value]
                    for col in range(1, ws.max_column + 1):
                        cell = ws[f"{get_column_letter(col)}{row}"]
                        cell.font = Font(bold=True)
                        cell.fill = PatternFill(start_color=current_group_color,
                                                end_color=current_group_color, fill_type="solid")
                elif current_group_color and current_data_color:
                    for col in range(1, ws.max_column + 1):
                        cell = ws[f"{get_column_letter(col)}{row}"]
                        cell.fill = PatternFill(start_color=current_data_color,
                                                end_color=current_data_color, fill_type="solid")

        # Add hyperlinks from Summary -> per-Digital ID sheets
        if "Summary" in wb.sheetnames:
            ws_summary = wb["Summary"]
            for row in range(2, ws_summary.max_row + 1):
                digital_id = ws_summary[f"A{row}"].value
                file_extension = ws_summary[f"B{row}"].value
                if digital_id in digital_id_data:
                    sheet_name = f"'{digital_id}'" if " " in digital_id else digital_id
                    # Link the Digital ID cell
                    ws_summary[f"A{row}"].hyperlink = f"#{sheet_name}!A1"
                    ws_summary[f"A{row}"].font = Font(color="0000FF", underline="single")
                    # Link the File Extension cell to first match on that sheet
                    if digital_id in wb.sheetnames:
                        sheet = wb[digital_id]
                        for sheet_row in range(2, sheet.max_row + 1):
                            if sheet[f"A{sheet_row}"].value == file_extension:
                                ws_summary[f"B{row}"].hyperlink = f"#{sheet_name}!A{sheet_row}"
                                ws_summary[f"B{row}"].font = Font(color="0000FF", underline="single")
                                break

        wb.save(file_name)

    # -----------------------------------
    # Remove temp CSVs (robust to bare names)
    # -----------------------------------
    def cleanup_temp_csvs(self, temp_files):
        for csv_file in temp_files:
            p = Path(str(csv_file))
            if not p.is_absolute():
                p = TEMP_DIR / p.name.lstrip("/\\")
            try:
                p.unlink(missing_ok=True)
            except Exception as e:
                print(f"Warning: couldn’t remove {p}: {e}")
