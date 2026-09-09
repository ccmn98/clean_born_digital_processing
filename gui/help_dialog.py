from pathlib import Path

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import (
    QDialog,
    QTextBrowser,
    QVBoxLayout,
    QDialogButtonBox,
)
class HelpDialog(QDialog):
    def __init__(self, html_path, title, replacements=None, parent=None):
        
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(900, 700)

        layout = QVBoxLayout(self)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        
        html_path = Path(html_path).resolve()

        html_content = html_path.read_text(encoding="utf-8")

        if replacements:
            for key, value in replacements.items():
                placeholder = f"{{{{{key}}}}}"
                html_content = html_content.replace(
                    placeholder,
                    str(value),
                )

        self.browser.document().setBaseUrl(QUrl.fromLocalFile(str(html_path.parent) + "/"))
            
        self.browser.setHtml(html_content)
            

        layout.addWidget(self.browser)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Close
        )
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)