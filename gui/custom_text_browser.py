from PyQt5.QtWidgets import QTextBrowser
from PyQt5.QtCore import QUrl

import os


class CustomTextBrowser(QTextBrowser):
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)

        self.main_window = main_window

        # Prevent QTextBrowser from trying to display the file itself
        self.setOpenExternalLinks(False)

        self.anchorClicked.connect(self.handle_link_click)

    def handle_link_click(self, url: QUrl):
        """Open clicked files using the Windows default application."""

        if url.scheme() == "file":
            file_path = url.toLocalFile()

            try:
                os.startfile(file_path)

            except Exception as e:
                print(
                    f"Failed to open file with default application: {e}"
                )
