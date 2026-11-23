# main.py (Entry Point)

import sys
import os
import subprocess
from pathlib import Path
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon, QFont
import re
# Now import DirOutputApp correctly
from gui.main_window import DirOutputApp
from workers.file_extension_scan import FileExtensionScanWorker
from core.config import LOG_DIR, ensure_app_directories

from logging.handlers import RotatingFileHandler

APP_DIR = Path.home() / ".BornDigitalProcessing"
LOG_DIR = APP_DIR / "logs"

def setup_logging(log_dir, level=logging.DEBUG):
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(level)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | "
        "%(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = RotatingFileHandler(
        log_dir / "born_digital_processing.log",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
def resource_path(relative_path):
    """Return the correct resource path for development and PyInstaller."""
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent

    return base_path / relative_path

def main():
    #Starting log and temp files
    ensure_app_directories()
    
    # Start the Flask server as a background process
    setup_logging(LOG_DIR)    
    logging.info("Application starting")
    logging.info("Starting Flask server...")
    try:
        subprocess.Popen([sys.executable, "open_file_server.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info("Flask server started successfully.")
    except Exception:
        logging.exception("Failed to start Flask server")
    
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "LibraryOfCongress.BornDigitalProcessing"
        )
      
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Set the default font for the application
    font = QFont("Times", 8)
    app.setFont(font)
    window = DirOutputApp()
    icon_path = resource_path("core/images/US-LibraryOfCongress-Logo.ico")
    print(f"Icon path: {icon_path}")
    print(f"Icon exists: {icon_path.exists()}")

    app.setWindowIcon(QIcon(str(icon_path)))
    window = DirOutputApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()