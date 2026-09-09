import os
import json
import shutil
import subprocess
import datetime as dt
import re
from pathlib import Path

def find_wkhtmltopdf():
    print("Working")


    # 0) Look in THIS project: core/executables/wkhtmltopdf/bin/
    project_embedded_1 = Path(__file__).resolve().parent.parent/ "core" / "executables" / "wkhtmltopdf" / "bin" / "wkhtmltopdf.exe"
    
    print(f"project_embedded_1: {project_embedded_1}")
    
    # project_embedded_2 = Path(r"C:\Users\MSS PREP\Documents\GitHub\born-digital-processing\core\executables\wkhtmltopdf\bin\wkhtmltopdf.exe")
    
    # print(f"project_embedded_2: {project_embedded_2}")
    
    if project_embedded_1.is_file():
        print(f"[filefmt] Using embedded wkhtmltopdf in project_embedded_1: {project_embedded_1}")
        return str(project_embedded_1)
    
    # if project_embedded_2.is_file():
    #     print(f"[filefmt] Using embedded wkhtmltopdf in project_embedded_2: {project_embedded_2}")
    #     return str(project_embedded_2)

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

find_wkhtmltopdf()