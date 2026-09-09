from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtCore import Qt



class EventLineEdit(QLineEdit):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        
    def keyPressEvent(self, event):
        # Check if the key pressed is Spacebar or Enter
        if event.key() == Qt.Key_Space or event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:

            # Retrieve the required fields from the main window (DirOutputApp)
            collection_id = self.main_window.bagger_info_dict["Id"]
            registration_no = self.main_window.entry_file_name_registration_no_field.text()
            drive_text = self.main_window.entry_file_name_media_no_drives_field.text()
            directory_text = self.main_window.entry_file_name_media_no_directories_field.text()

            # Call the method with the required arguments
            self.main_window.space_enter_media_nos(collection_id, registration_no, drive_text, directory_text)

        # Check if the key pressed is Comma
        elif event.key() == Qt.Key_Comma:
            print(f"Comma pressed in {self.objectName()}")

        else:
            # Call the parent class's keyPressEvent for default behavior
            super().keyPressEvent(event)