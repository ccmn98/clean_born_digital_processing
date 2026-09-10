from pathlib import Path

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton


class HelpDialog(QDialog):
    def __init__(self, html_path, title, parent=None):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(900, 700)

        layout = QVBoxLayout(self)

        self.browser = QTextBrowser()
        layout.addWidget(self.browser)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        html_path = Path(html_path)
        css_path = html_path.parent / "user_guide.css"

        html = html_path.read_text(
            encoding="utf-8"
        )

        # Lets relative image paths such as
        # images/figure01_main_window.png resolve correctly.
        self.browser.document().setBaseUrl(
            QUrl.fromLocalFile(str(html_path.parent) + "/")
        )

        # Apply the CSS directly to QTextBrowser.
        if css_path.exists():
            css = css_path.read_text(
                encoding="utf-8"
            )
            self.browser.document().setDefaultStyleSheet(css)

        self.browser.setHtml(html)