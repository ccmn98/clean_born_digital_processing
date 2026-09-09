from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QVBoxLayout,
)


class DeselectDialog(QDialog):
    def __init__(
        self,
        drives,
        directories,
        drive_digital_ids,
        directory_digital_ids,
        parent=None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Deselect Drives, Directories, or Digital IDs")
        self.resize(650, 450)

        self.selected_drives_list = drives
        self.selected_directories_list = directories
        self.formatted_drive_digital_ids_list = drive_digital_ids
        self.formatted_directory_digital_ids_list = directory_digital_ids

        self.drive_checkboxes = []
        self.directory_checkboxes = []
        self.drive_id_checkboxes = []
        self.directory_id_checkboxes = []

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Selected drives
        drive_group = QGroupBox("Selected Drives")
        drive_layout = QVBoxLayout(drive_group)

        if self.selected_drives_list:
            for drive in self.selected_drives_list:
                checkbox = QCheckBox(drive)
                drive_layout.addWidget(checkbox)
                self.drive_checkboxes.append(checkbox)
        else:
            checkbox = QCheckBox("No drives selected")
            checkbox.setEnabled(False)
            drive_layout.addWidget(checkbox)

        main_layout.addWidget(drive_group)

        # Drive digital IDs
        drive_id_group = QGroupBox("Drive / Removable Media Digital IDs")
        drive_id_layout = QVBoxLayout(drive_id_group)

        if self.formatted_drive_digital_ids_list:
            for digital_id in self.formatted_drive_digital_ids_list:
                checkbox = QCheckBox(digital_id)
                drive_id_layout.addWidget(checkbox)
                self.drive_id_checkboxes.append(checkbox)
        else:
            checkbox = QCheckBox("No drive digital IDs entered")
            checkbox.setEnabled(False)
            drive_id_layout.addWidget(checkbox)

        main_layout.addWidget(drive_id_group)

        # Selected directories
        directory_group = QGroupBox("Selected Directories")
        directory_layout = QVBoxLayout(directory_group)

        if self.selected_directories_list:
            for directory in self.selected_directories_list:
                checkbox = QCheckBox(directory)
                directory_layout.addWidget(checkbox)
                self.directory_checkboxes.append(checkbox)
        else:
            checkbox = QCheckBox("No directories selected")
            checkbox.setEnabled(False)
            directory_layout.addWidget(checkbox)

        main_layout.addWidget(directory_group)

        # Directory digital IDs
        directory_id_group = QGroupBox("Directory Digital IDs")
        directory_id_layout = QVBoxLayout(directory_id_group)

        if self.formatted_directory_digital_ids_list:
            for digital_id in self.formatted_directory_digital_ids_list:
                checkbox = QCheckBox(digital_id)
                directory_id_layout.addWidget(checkbox)
                self.directory_id_checkboxes.append(checkbox)
        else:
            checkbox = QCheckBox("No directory digital IDs entered")
            checkbox.setEnabled(False)
            directory_id_layout.addWidget(checkbox)

        main_layout.addWidget(directory_id_group)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def get_selected_items(self):
        selected_drives = [
            checkbox.text()
            for checkbox in self.drive_checkboxes
            if checkbox.isChecked()
        ]

        selected_directories = [
            checkbox.text()
            for checkbox in self.directory_checkboxes
            if checkbox.isChecked()
        ]

        selected_drive_digital_ids = [
            checkbox.text()
            for checkbox in self.drive_id_checkboxes
            if checkbox.isChecked()
        ]

        selected_directory_digital_ids = [
            checkbox.text()
            for checkbox in self.directory_id_checkboxes
            if checkbox.isChecked()
        ]

        return (
            selected_drives,
            selected_directories,
            selected_drive_digital_ids,
            selected_directory_digital_ids,
        )