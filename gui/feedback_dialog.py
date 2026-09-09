from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout, 
    QFileDialog,QListWidget,
    QCheckBox,
)

from pathlib import Path
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
import json
import platform
import shutil
import sys
import tempfile
import zipfile

class FeedbackDialog(QDialog):
    def __init__(self, log_excerpt="", parent=None):
        super().__init__(parent)

        self.setWindowTitle("Report an Issue or Suggestion")
        self.resize(700, 750)

        self.screenshot_paths = []

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Report type
        self.report_type = QComboBox()
        self.report_type.addItems([
            "Bug",
            "Suggestion",
            "Other",
        ])

        # Title
        self.title_edit = QLineEdit()

        # Description
        self.description_edit = QPlainTextEdit()
        self.description_edit.setMinimumHeight(120)

        # Additional comments
        self.comments_edit = QPlainTextEdit()
        self.comments_edit.setMinimumHeight(80)

        form_layout.addRow(
            "Report type:",
            self.report_type,
        )

        form_layout.addRow(
            "Title:",
            self.title_edit,
        )

        form_layout.addRow(
            "What happened?",
            self.description_edit,
        )

        form_layout.addRow(
            "Additional comments:",
            self.comments_edit,
        )

        layout.addLayout(form_layout)

        # Screenshot attachment
        self.screenshot_button = QPushButton(
            "Attach Screenshot(s)"
        )
        self.screenshot_button.clicked.connect(
            self.add_screenshots
        )

        layout.addWidget(self.screenshot_button)

        self.screenshot_list = QListWidget()
        layout.addWidget(self.screenshot_list)

        # Include log checkbox
        self.include_log_checkbox = QCheckBox(
            "Include recent application activity and file paths"
        )
        self.include_log_checkbox.setChecked(True)

        layout.addWidget(self.include_log_checkbox)

        # Recent application log
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlainText(log_excerpt)
        self.log_edit.setMinimumHeight(180)

        form_layout.addRow(
            "Recent Application Activity:",
            self.log_edit,
        )

        # Save / Cancel buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Save
            | QDialogButtonBox.Cancel
        )

        self.buttons.accepted.connect(
            self.save_report
        )
        self.buttons.rejected.connect(
            self.reject
        )

        layout.addWidget(self.buttons)
          
            
    def add_screenshots(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Screenshot(s)",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )

        for file_path in files:
            if file_path not in self.screenshot_paths:
                self.screenshot_paths.append(file_path)
                self.screenshot_list.addItem(Path(file_path).name)        
                
                
    def save_report(self):
        """Save the bug or suggestion report as a ZIP file."""

        report_type = self.report_type.currentText()
        title = self.title_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        comments = self.comments_edit.toPlainText().strip()

        if not title:
            QMessageBox.warning(
                self,
                "Missing Title",
                "Please enter a short title for the report.",
            )
            return

        if not description:
            QMessageBox.warning(
                self,
                "Missing Description",
                "Please describe what happened or what you are suggesting.",
            )
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        suggested_name = (
            f"BornDigital_{report_type}_{timestamp}.zip"
        )

        zip_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Bug or Suggestion Report",
            suggested_name,
            "ZIP Files (*.zip)",
        )

        if not zip_path:
            return

        zip_path = Path(zip_path)

        if zip_path.suffix.lower() != ".zip":
            zip_path = zip_path.with_suffix(".zip")

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                report_dir = temp_path / "bug_report"
                report_dir.mkdir()

                screenshots_dir = report_dir / "screenshots"
                screenshots_dir.mkdir()

                # Load application version information
                project_root = Path(__file__).resolve().parent.parent
                version_file = project_root / "core" / "version.json"

                try:
                    with version_file.open(
                        "r",
                        encoding="utf-8",
                    ) as file:
                        version_info = json.load(file)
                except (
                    FileNotFoundError,
                    json.JSONDecodeError,
                    OSError,
                ):
                    version_info = {}

                # Get Python BagIt package version
                try:
                    bagit_version = version("bagit")
                except PackageNotFoundError:
                    bagit_version = "Not installed"

                # Build report text
                report_lines = [
                    "Born-Digital Processing Application",
                    "Bug / Suggestion Report",
                    "",
                    f"Report Type: {report_type}",
                    f"Title: {title}",
                    "",
                    "Application Information",
                    "-----------------------",
                    (
                        "Application Version: "
                        f"{version_info.get('version', 'Unknown')}"
                    ),
                    (
                        "Build: "
                        f"{version_info.get('build', 'Unknown')}"
                    ),
                    (
                        "Build Date: "
                        f"{version_info.get('build_date', 'Unknown')}"
                    ),
                    (
                        "Status: "
                        f"{version_info.get('status', 'Unknown')}"
                    ),
                    f"Python BagIt: {bagit_version}",
                    f"Python: {platform.python_version()}",
                    f"Operating System: {platform.platform()}",
                    f"Report Created: {datetime.now().astimezone()}",
                    "",
                    "Description",
                    "-----------",
                    description,
                    "",
                    "Additional Comments",
                    "-------------------",
                    comments or "None provided.",
                    "",
                ]

                # Add screenshot names
                if self.screenshot_paths:
                    report_lines.extend([
                        "Attached Screenshots",
                        "--------------------",
                    ])

                    for index, screenshot in enumerate(
                        self.screenshot_paths,
                        start=1,
                    ):
                        source = Path(screenshot)

                        screenshot_name = (
                            f"screenshot_{index}{source.suffix.lower()}"
                        )

                        destination = (
                            screenshots_dir / screenshot_name
                        )

                        shutil.copy2(
                            source,
                            destination,
                        )

                        report_lines.append(screenshot_name)

                    report_lines.append("")

                # Write main report
                report_file = report_dir / "bug_report.txt"

                report_file.write_text(
                    "\n".join(report_lines),
                    encoding="utf-8",
                )

                # Save recent log separately
                if (
                    self.include_log_checkbox.isChecked()
                    and self.log_edit.toPlainText().strip()
                ):
                    log_file = report_dir / "recent_log.txt"

                    log_file.write_text(
                        self.log_edit.toPlainText(),
                        encoding="utf-8",
                    )

                # Create ZIP
                with zipfile.ZipFile(
                    zip_path,
                    "w",
                    compression=zipfile.ZIP_DEFLATED,
                ) as archive:

                    for file_path in report_dir.rglob("*"):
                        if file_path.is_file():
                            archive.write(
                                file_path,
                                file_path.relative_to(report_dir),
                            )

            QMessageBox.information(
                self,
                "Report Saved",
                f"The report was saved successfully:\n\n{zip_path}",
            )

            self.accept()

        except OSError as exc:
            QMessageBox.critical(
                self,
                "Unable to Save Report",
                f"The report could not be saved.\n\n{exc}",
            )
            
        
        