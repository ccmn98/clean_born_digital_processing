from email import message
import socket
import tempfile

from PyQt5.QtCore import Qt, QThread

from PyQt5.QtWidgets import QMainWindow, QAction, QMenu, QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QLabel, QTextEdit, QGridLayout, QComboBox, QLineEdit, QCheckBox, QMessageBox, QFileDialog, QDialog, QApplication, QCheckBox, QWidgetAction, QProgressBar

from PyQt5.QtGui import QFont, QIcon

import glob
import os
import json
import webbrowser
import subprocess
import sys
from pathlib import Path
from collections import deque

from workers.directory_listing import DirectoryListingWorker
from workers.file_extension_scan import FileExtensionScanWorker
from workers.file_format_scan_worker import FileFormatScanWorker
from workers.bagger_worker import BaggingWorker
from workers.byte_count_worker import ByteCountWorker

from gui.custom_text_browser import CustomTextBrowser
from gui.deselect_dialog import DeselectDialog
from gui.event_line_edit import EventLineEdit
from gui.feedback_dialog import FeedbackDialog

from managers.output_manager import OutputManager
import re
import inspect
import html

from jinja2 import Environment, FileSystemLoader, select_autoescape

from gui.help_dialog import HelpDialog

from importlib.metadata import PackageNotFoundError, version

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CORE_DIR = PROJECT_ROOT / "core"
VERSION_FILE = CORE_DIR / "version.json"
HELP_DOCS_DIR = CORE_DIR / "help_docs"


import logging
logger = logging.getLogger(__name__)
from logging.handlers import RotatingFileHandler

class DirOutputApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("born_digital_processing")
        # Create an instance of CustomTextBrowser and pass self (main_window)
        self.output_text = CustomTextBrowser(main_window=self)
        
        # Start the Flask server
        self.start_flask_server()
        
        self.output_directory = ""
        self.preserve_output = False
        self.output_manager = None
        
         # Drives
        self.selected_drives_list = []
        
        self.completed_drives_dir_list = []
        self.media_numbers_drive_list = []
        self.formatted_drive_digital_ids_list = []
        self.selected_drives_digID_dictionary = {}
        
        # Directories
        self.selected_directories_list = []
        self.completed_dir_directory_list = []
        self.media_numbers_directories_list = []
        self.formatted_directory_digital_ids_list = []
        self.selected_directories_digID_dictionary = {}
        
        #dictionary to store information from the bagger profile JSON file
        self.bagger_info_dict = {}
        
        #dictionary and string variable for output directory
        self.output_directory = ''
        print(f"self.self.output_directory: {self.output_directory}")
        
        self.output_dir_dictionary = {}
        self.logger.debug(f"output_dir_dictionary initialized: {self.output_dir_dictionary}")
        print(f"self.output_dir_dictionary: {self.output_dir_dictionary}")
        
        self.preserve_output_directory_list = []
        
        #completed directories and drives
        self.completed_dir_drives = {}
        
        self.init_ui()
        
        self.create_menu()
        
# Create temporary HTML file used by the GUI output display
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".html",
            prefix="born_digital_intake_",
            delete=False
        )

        self.temp_html_path = temp_file.name
        print(f"GUI temporary HTML path: {self.temp_html_path}")
        temp_file.close()

        # Output Manager handling the GUI display
        self.output_manager = OutputManager(
            self.output_text,
            html_file_path=self.temp_html_path,
            parent=self
        )
            
        
        
    # Used to easily update fields in the Jinja2 template and GUI display
    def update_output_display(self):
        self.output_manager.update_display(
        self.selected_drives_list,
        self.selected_directories_list,
        self.formatted_drive_digital_ids_list,
        self.formatted_directory_digital_ids_list,
        self.output_directory,
        self.selected_drives_digID_dictionary,
        self.selected_directories_digID_dictionary
    )

    def closeEvent(self, event):
        try:
            if os.path.exists(self.temp_html_path):
                os.remove(self.temp_html_path)
        except OSError as e:
            print(f"Could not remove temporary HTML file: {e}")

        event.accept()
    
    def create_aligned_checkbox_menu_item(self, label_text):
        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setHorizontalSpacing(20)

        label = QLabel(label_text)
        checkbox = QCheckBox()

        layout.addWidget(label, 0, 0, alignment=Qt.AlignLeft)
        layout.addWidget(checkbox, 0, 1, alignment=Qt.AlignRight)

        action = QWidgetAction(container)
        action.setDefaultWidget(container)
        return action, checkbox
    
    def create_menu_link_item(self, label_text, submenu: QMenu):
        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(10, 2, 10, 2)

        label = QLabel()
        label.setText(f'{label_text} <span style="font-size:14pt; vertical-align: -4px;">▶</span>')
        label.setTextFormat(Qt.RichText)
        layout.addWidget(label, 0, 0, 1, 2)

        action = QWidgetAction(self)
        action.setDefaultWidget(container)
        action.setMenu(submenu)  # attach actual submenu

        return action
    
    # Creating a file menu to save/load profiles, 
    def create_menu(self):
        menubar = self.menuBar()

        # --- Running Menu ---
        running_options_menu = menubar.addMenu('Processing Tasks')

        # Directory Listing
        directory_action, self.directory_checkbox = self.create_aligned_checkbox_menu_item("Directory Listing")
        special_file_exten_action, self.special_file_exten_actio_checkbox = self.create_aligned_checkbox_menu_item("Scan for Limited File Extensions")
        bagger_action, self.bagger_checkbox = self.create_aligned_checkbox_menu_item("Create Bag")
        #exiftool_action, self.exiftool_checkbox = self.create_aligned_checkbox_menu_item("Exiftool")
        byte_count_action, self.byte_count_checkbox = self.create_aligned_checkbox_menu_item("Byte Count")
        
        running_options_menu.addAction(directory_action)
        running_options_menu.addAction(special_file_exten_action)
        running_options_menu.addAction(bagger_action)
        #running_options_menu.addAction(exiftool_action)
        running_options_menu.addAction(byte_count_action)

        # --- File Format Submenu ---
        #file_format_menu = QMenu('File Format', self)
        
        file_format_menu = QMenu(self)
        file_format_action = self.create_menu_link_item("File Format", file_format_menu)
        running_options_menu.addAction(file_format_action)

        # Output Selection Submenu
        output_file_format_selection_menu = QMenu('Output Selection', self)
        
        excel_action, self.excel_checkbox = self.create_aligned_checkbox_menu_item("Excel Output")
        html_action, self.html_checkbox = self.create_aligned_checkbox_menu_item("HTML Output")
        pdf_action, self.pdf_checkbox = self.create_aligned_checkbox_menu_item("PDF Output")

        output_file_format_selection_menu.addAction(excel_action)
        output_file_format_selection_menu.addAction(html_action)
        output_file_format_selection_menu.addAction(pdf_action)

        # Signature update submenu
        pronom_signature_menu = QAction('Signature update', self)
        pronom_signature_menu.triggered.connect(self.run_pronom_signature_update)
        
        #pronom_signature_update = QAction('Signature 1 update', self)
        file_format_menu.addAction(pronom_signature_menu)

        # Add submenus to File Format menu
        file_format_menu.addMenu(output_file_format_selection_menu)
        file_format_menu.addAction(pronom_signature_menu)

        # Add File Format to Running menu
        running_options_menu.addMenu(file_format_menu)

        
        # output_file_format_selection = running_options_menu.addMenu('Output Selection')
    
        # --- Help Menu ---
        help_menu = menubar.addMenu('Help')
        user_guide_action = QAction("User Guide...", self)
        user_guide_action.triggered.connect(self.show_user_guide)
        help_menu.addAction(user_guide_action)

        report_action = QAction(
            "Report a Bug or Suggestion...",
            self,
        )
        report_action.triggered.connect(
            self.show_report_issue_help
        )
        help_menu.addAction(report_action)

        help_menu.addSeparator()

        about_action = QAction("About...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)


            
    def init_ui(self):
        
        
        ## Label of the window/program
        self.setWindowTitle("Born-Digital Processing Application") 
        # self.setFont(QFont(font_family, font_size))
        self.setGeometry(375, 150,1200, 600)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
          
        # self.deselect_directory_button = QPushButton("Deselect Directory/Drive")
        # self.deselect_directory_button.setFont(QFont(font_family, font_size))
        # self.deselect_directory_button.clicked.connect(self.deselect_items)
        
        # Create the main layout
        main_layout = QHBoxLayout()
        self.central_widget.setLayout(main_layout)
        # self.central_widget.setFont(QFont(font_family, font_size))
        
        #Create layout for printed output section
        self.printed_output_widget = QWidget()
        self.printed_output_layout = QVBoxLayout()
        self.printed_output_widget.setLayout(self.printed_output_layout)
        self.printed_output_label = QLabel("<b>Script Output Window</b>")
        self.printed_output_label.setAlignment(Qt.AlignCenter)
        self.output_text = QTextEdit()
        self.output_text = CustomTextBrowser(main_window=self)
        self.output_text.setReadOnly(True)

        
# Apply font settings to all QLabel and QCheckBox widgets
        
        # Create the layout for the confirming drive and directory selections section
        select_drive_layout = QVBoxLayout()
       
        # Create the Selected Items widget and Window
        # Selected items text window
        self.selected_drives_widget = QWidget() 
        self.selected_drives_layout = QVBoxLayout()
        self.selected_drives_widget.setLayout(self.selected_drives_layout)    
        self.selected_drives_label = QLabel("<b>Selected Drives:</b>")
        self.selected_drives_text = QTextEdit()
        self.selected_drives_text.setReadOnly(True)
    
        
        # Create the Selected Items widget and Window
        # Selected items text window
        self.selected_directories_widget = QWidget()
        self.selected_directories_layout = QVBoxLayout()
        self.selected_directories_widget.setLayout(self.selected_directories_layout)
        self.selected_directories_label = QLabel("<b>Selected Directory Items:</b>")
        self.selected_directories_text = QTextEdit()
        self.selected_directories_text.setReadOnly(True)
        
        ## Deselect button
        self.deselect_selected_items_button = QPushButton("THIS ONE Deselect Selected Items")
        self.deselect_selected_items_button.clicked.connect(self.deselect_selected_items)
        # self.selected_drives_layout.addWidget(self.selected_drives_label)
        # self.selected_drives_layout.addWidget(self.selected_drives_text)
        

        # Add the Selected Items widget to the left layout
        select_drive_layout.addWidget(self.selected_drives_widget)
        self.selected_directories_layout.addWidget(self.selected_directories_label)
        # self.selected_directories_layout.addWidget(self.selected_directories_text)  # Add QTextEdit widget here
        #select_drive_layout.addWidget(self.selected_directories_widget)
        # select_drive_layout.addWidget(self.deselect_directory_button)
        
        # Create the layout for the section where a user enters information
        self.user_entry_layout = QGridLayout()
        
        # Add the left and right layouts to the main layout
        main_layout.addLayout(self.user_entry_layout)
        main_layout.addLayout(select_drive_layout)   
        
        # Add the printed output section to the main layout
        self.printed_output_layout.addWidget(self.printed_output_label)
        self.printed_output_layout.addWidget(self.output_text)  # Add the QTextEdit to printed_output_layout 
        main_layout.addWidget(self.printed_output_widget)  # Add the printed_output_widget to main_layout

        # Add your current widgets to the right layout
        # Get the user's home directory and construct the path
        home_dir = os.path.expanduser('~')
        self.bagger_profile_target_path = os.path.join(home_dir, 'bagger')

        # Find all JSON files in the target directory
        json_files = glob.glob(os.path.join(self.bagger_profile_target_path, '*.json'))

        # Filter JSON files based on the criteria
        self.matching_files, self.project_titles = self.filter_json_files(json_files)

        # Create a dropdown menu for selecting JSON files
        self.Bagger_JSON_file_combo_box = QComboBox()
        self.Bagger_JSON_file_combo_box.addItem("")  # Add a blank entry for the initial state
        for project_title in self.project_titles:
            self.Bagger_JSON_file_combo_box.addItem(project_title)


        self.Bagger_JSON_file_combo_box.currentIndexChanged.connect(self.load_json_file)
        
        # Add the dropdown menu for selecting JSON files first
        self.user_entry_layout.addWidget(QLabel(f"<b>Select a JSON file from:</b> {self.bagger_profile_target_path}:"), 0, 0, 1, 2)
        self.user_entry_layout.addWidget(self.Bagger_JSON_file_combo_box, 1, 0, 1, 2)
        
        # Create a pull down menu to select the profile
        self.user_entry = [
            ('LC Project:', 'LC-Project'),
            ('Event-Agent', 'Event-Agent'),
            ('Mss-Contact-Info', 'MSS-Contact-Info'),
            ('Restrictions', 'Restrictions'),
            ('LC-LCCN', 'LC-LCCN'),
            ('Enter the <b>collection number</b>:', 'Id')   
            
        ]
        self.user_entry_fields = {}
        
        row = 2

        
        for display_name, field_key in self.user_entry:
            label = QLabel(display_name)
            line_edit = QLineEdit()
            if field_key == 'Event-Agent':  # Displaying a list of bagging agents linked to the collection
                agents_combo_box = QComboBox()
                agents_combo_box.currentIndexChanged.connect(self.update_event_agent)
                self.user_entry_layout.addWidget(label, row, 0)
                self.user_entry_layout.addWidget(agents_combo_box, row, 1)
                self.user_entry_fields[field_key] = agents_combo_box
            elif field_key == 'MSS-Contact-Info':  # Used for displaying as LC address
                self.mss_contact_text_edit = QTextEdit()
                self.mss_contact_text_edit.setFixedSize(250, 75)
                self.user_entry_layout.addWidget(label, row, 0)
                self.user_entry_layout.addWidget(self.mss_contact_text_edit, row, 1)
                self.user_entry_fields[field_key] = self.mss_contact_text_edit
            elif field_key == 'LC-Project':  # Used for displaying project name
                self.LC_Project_text_edit = QTextEdit()
                self.user_entry_layout.addWidget(label, row, 0)
                self.user_entry_layout.addWidget(self.LC_Project_text_edit, row, 1)
                self.user_entry_fields[field_key] = self.LC_Project_text_edit   
            elif field_key == 'Restrictions':  # Used for displaying restrictions
                self.restrictions_text_edit = QTextEdit()
                self.user_entry_layout.addWidget(label, row, 0)
                self.user_entry_layout.addWidget(line_edit, row, 1)
                self.user_entry_fields[field_key] = line_edit   
            elif field_key == 'LC-LCCN':  # Used for displaying LCCN
                self.LCCN_text_edit = QTextEdit()
                self.LCCN_text_edit.setReadOnly(True)
                self.user_entry_layout.addWidget(label, row, 0)
                self.user_entry_layout.addWidget(line_edit, row, 1)
                self.user_entry_fields[field_key] = line_edit
                
            elif field_key == 'Id':  # Used for Collection Number
                self.label_file_name = QLabel("<b>Enter the file name (without extension):</b>")
                self.user_entry_layout.addWidget(self.label_file_name, row, 0)
                row += 1
                self.collection_text_edit = QTextEdit()

                self.user_entry_layout.addWidget(label, row, 0)
                self.collection_text_edit.setContentsMargins(20, 0, 0, 0)
                label.setContentsMargins(20, 0, 0, 0)
                self.user_entry_layout.addWidget(line_edit, row, 1)
                self.user_entry_fields[field_key] = line_edit     

            else:
                line_edit = QLineEdit()
                line_edit.setReadOnly(True)
                self.user_entry_layout.addWidget(label, row, 0)
                self.user_entry_layout.addWidget(line_edit, row, 1)
                self.user_entry_fields[field_key] = line_edit
            row += 1
            
        
        ##User entry for registration number
         #Label
        self.label_file_name_registration_no = QLabel("Enter the <b>registration number</b>:")
        self.label_file_name_registration_no.setContentsMargins(20, 0, 0, 0)
        self.user_entry_layout.addWidget(self.label_file_name_registration_no, row, 0)
        #Entry
        self.entry_file_name_registration_no_field = QLineEdit()
        self.entry_file_name_registration_no_field.setStyleSheet("QLineEdit {color: rgba(0, 0, 0, 100); }")
        self.entry_file_name_registration_no_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.entry_file_name_registration_no_field.editingFinished.connect(self.validate_registration_number)
        self.user_entry_layout.addWidget(self.entry_file_name_registration_no_field, row, 1)
        
        row += 1
        
        ##User entry for media number
        ##Label
        self.label_file_name_media_count_number_label = QLabel("Media Count Number")
        self.label_file_name_media_count_number_label.setContentsMargins(20, 0, 0, 0)
        self.user_entry_layout.addWidget(self.label_file_name_media_count_number_label, row, 0)
        
        row += 1
        
        #User directory_number label
        self.file_name_media_no_directories_label = QLabel("<b>Directories</b>:")
        self.file_name_media_no_directories_label.setContentsMargins(30, 0, 0, 0)
        self.user_entry_layout.addWidget(self.file_name_media_no_directories_label, row, 0)
        #User directory_number entry
        self.entry_file_name_media_no_directories_field = EventLineEdit(self)
        self.entry_file_name_media_no_directories_field.setStyleSheet("QLineEdit {color: rgba(0, 0, 0, 100); }")
        self.entry_file_name_media_no_directories_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.user_entry_layout.addWidget(self.entry_file_name_media_no_directories_field, row, 1)
        
        row += 1
        
        #Label for drives
        self.file_name_media_no_drives_label = QLabel("<b>Drives</b>:")
        self.file_name_media_no_drives_label.setContentsMargins(30, 0, 0, 0)
        self.user_entry_layout.addWidget(self.file_name_media_no_drives_label, row, 0)
        #User drive_number entry
        self.entry_file_name_media_no_drives_field = EventLineEdit(self)
        self.entry_file_name_media_no_drives_field.setStyleSheet("QLineEdit {color: rgba(0, 0, 0, 100); }")
        self.entry_file_name_media_no_drives_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.user_entry_layout.addWidget(self.entry_file_name_media_no_drives_field, row, 1)
        
        row += 1
        
        ## Select Directory button--call function
        self.select_directory_button = QPushButton("Select Directory/Drive")
        self.select_directory_button.clicked.connect(self.select_directory)
        self.user_entry_layout.addWidget(self.select_directory_button, row, 0, 1, 2)

        
        row += 1
        
        ##Checkbox to save the path to the selected directory
        self.checkbox_preserve_output = QCheckBox("Preserve Output Directory")
        # self.checkbox_preserve_output.stateChanged.connect(self.update_preserve_status)
        self.checkbox_preserve_output.setStyleSheet("QCheckBox{padding-left: 20px;}")
        self.checkbox_preserve_output.stateChanged.connect(self.set_output_dir) # Preserve output directory
        # self.checkbox_preserve_output.stateChanged.connect(self.qcheckbox_status_method) 
        self.user_entry_layout.addWidget(self.checkbox_preserve_output, row, 0)
        
        #button to select the output directory
        self.select_output_dir_button = QPushButton("Select Output Directory")
        self.select_output_dir_button.clicked.connect(self.select_output_directory)  #select_directory
        self.user_entry_layout.addWidget(self.select_output_dir_button, row, 1)
        
        row += 1
        
        # Deselect Directory/Drive on the next row
        self.deselect_directory_button = QPushButton("Deselect Directory/Drive")
        self.deselect_directory_button.clicked.connect(self.deselect_items)
        self.user_entry_layout.addWidget(self.deselect_directory_button, row, 0, 1, 2)

        # move to the NEXT row so nothing overlaps the button
        row += 1
        
        # Confirm that the digital ID is correctly assigned to the correct path
        self.confirm_digital_ID_button = QPushButton("Confirm Digital ID")
        self.confirm_digital_ID_button.clicked.connect(self.confirm_directories_path_IDs)
        self.user_entry_layout.addWidget(self.confirm_digital_ID_button, row, 0)
        
        ##button to execute the program
        self.run_program_button = QPushButton("Run")
        self.run_program_button.clicked.connect(self.on_run_button_clicked)
        self.user_entry_layout.addWidget(self.run_program_button, row, 1)
        
        row += 1
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")
        self.user_entry_layout.addWidget(
            self.progress_bar,
            row,
            0,
            1,
            2
        )

        row += 1
        
        self.current_step_label = QLabel("Current Step: Ready")
        self.current_file_label = QLabel("Current File:")
        self.current_source_label = QLabel("Current Source:")

        self.current_step_label.setWordWrap(True)
        self.current_file_label.setWordWrap(True)
        self.current_source_label.setWordWrap(True)

        self.user_entry_layout.addWidget(self.current_step_label, row, 0, 1, 2)
        row += 1

        self.user_entry_layout.addWidget(self.current_file_label, row, 0, 1, 2)
        row += 1

        self.user_entry_layout.addWidget(self.current_source_label, row, 0, 1, 2)
        row += 1
        
        # ------------------------------
        # Current Activity label
        # ------------------------------
        self.current_activity_label = QLabel(
            "Current Activity: Ready"
        )
        self.current_activity_label.setWordWrap(True)

        self.user_entry_layout.addWidget(
            self.current_activity_label,
            row,
            0,
            1,
            2
        )

        row += 1
        
        
        
        # ------------------------------
        # Reset button
        # ------------------------------
        self.reset_state_button = QPushButton("Reset State")
        self.reset_state_button.clicked.connect(self.reset_state)
        self.user_entry_layout.addWidget(
            self.reset_state_button,
            row,
            0,
            1,
            2
        )

        row += 1

        # (optional) put labels below the button (or remove if unused)
        self.selected_directory_label = QLabel()
        self.selected_drive_label = QLabel()
        self.user_entry_layout.addWidget(self.selected_directory_label, row, 0, 1, 2)
        
        
        self.run_button_color = "gray"
        
    def update_progress(self, value, message=""):
        value = max(0, min(100, int(value)))

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)

        if message:
            self.progress_bar.setFormat(f"{value}% - {message}")
        else:
            self.progress_bar.setFormat(f"{value}%") 
            
    def start_indeterminate_progress(self, message="Working..."):
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat(message)


    def finish_progress(self, message="Complete"):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(f"100% - {message}")


    def reset_progress(self):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")       
            
    # Update PRONOM signatures    
    def run_pronom_signature_update(self):
        self.output_manager.log_message(
            "Updating PRONOM signatures using sf -update..."
        )

        here = Path(__file__).resolve()
        project_root = here.parent.parent
        
        sf_path = project_root / "core" / "executables" / "sf.exe"

        process = subprocess.Popen(
            [str(sf_path), "-update"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        for line in process.stdout:
            message = line.strip()
            if message:
                self.output_manager.log_message(message)
        

            
    # Filter for MSS JSON files
    def filter_json_files(self, json_files):
        matching_files = []
        project_titles = []
        for file_path in json_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    # Check if the JSON contains the required criteria
                    for item in data.get("ordered", []):
                        if "LC-Project" in item and item["LC-Project"]["requiredValue"].startswith("MSS"):
                            matching_files.append(file_path)
                            project_titles.append(item["LC-Project"]["requiredValue"])
                            break
                except (json.JSONDecodeError, KeyError):
                    continue
        return matching_files, project_titles
    
    
    # Build User profile filename
    
    def build_profile_filename(self, event_agent: str, lc_project: str) -> str:
    # Convert "Last, First" → "First_Last"
        event_agent = event_agent.strip()
        if "," in event_agent:
            last, first = [p.strip() for p in event_agent.split(",", 1)]
            agent_part = f"{first}_{last}"
        else:
            # If name not in comma format, just replace spaces
            agent_part = event_agent.replace(" ", "_")

        # ---- LC Project (e.g. "MSS--Carlene Sobrino Bonnivier papers") ----
        project = lc_project.strip()
        project_part = ""

        lower = project.lower()

        # Look for "papers" or "records"
        if "papers" in lower:
            target = "papers"
        elif "records" in lower:
            target = "records"
        else:
            target = None

        if target:
            words = project.split()
            # find index of the target word
            try:
                idx = [w.lower() for w in words].index(target)
                if idx > 0:
                    project_part = words[idx - 1].strip()
                    # Normalize spaces/hyphens
                    project_part = project_part.replace(" ", "_").replace("-", "_")
            except ValueError:
                project_part = ""

        # Final assembly
        if project_part:
            filename = f"{agent_part}_{project_part}_profile.json"
        else:
            filename = f"{agent_part}_profile.json"

        # Clean up double underscores
        filename = filename.replace("__", "_")

        return filename

    
    # Make fields read only
    def open_file_location(self, link):
        path = link[8:]  # Remove "file:///" prefix
        if os.path.isdir(path):
            webbrowser.open(path)
        else:
            path = os.path.dirname(path)
            webbrowser.open(path)
                
    def make_line_edit_read_only(self):
        self.line_edit.setReadOnly(True)
        
    def make_text_edit_read_only(self, event=None):
        self.text_edit.setReadOnly(True)
        if event is not None:
            super(QTextEdit, self.text_edit).focusOutEvent(event)
            

    
    # Load JSON Files
    
    def load_json_file(self, index):
        # Clear the current QLineEdit fields, QComboBox items, and QTextEdit content
        for field in self.user_entry_fields:
            if isinstance(self.user_entry_fields[field], QLineEdit):
                self.user_entry_fields[field].clear()
            elif isinstance(self.user_entry_fields[field], QComboBox):
                self.user_entry_fields[field].clear()
            elif isinstance(self.user_entry_fields[field], QTextEdit):
                self.user_entry_fields[field].clear()
        

        # Check if the selected index corresponds to a valid file
        if index == 0 or index - 1 >= len(self.matching_files):
            return

        self.bagger_profile_file_path = self.matching_files[index - 1]  # Adjust for the blank entry
        with open(self.bagger_profile_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Display the fields from the JSON file
        logging.debug(f"Loaded JSON data: {data}")  # Debugging line
        for item in data.get("ordered", []):
            for key, value in item.items():
                if key in self.user_entry_fields:
                    if 'requiredValue' in value:
                        if isinstance(self.user_entry_fields[key], QLineEdit):
                            self.user_entry_fields[key].setText(value['requiredValue'])
                            self.user_entry_fields[key].setReadOnly(True)
                        elif isinstance(self.user_entry_fields[key], QTextEdit):
                            self.user_entry_fields[key].setPlainText(value['requiredValue'])
                            self.user_entry_fields[key].setReadOnly(True)
                        
                    elif 'defaultValue' in value:
                        if isinstance(self.user_entry_fields[key], QLineEdit):
                           self.user_entry_fields[key].setText(value['defaultValue'])
                           self.user_entry_fields[key].setReadOnly(True)
                        elif isinstance(self.user_entry_fields[key], QTextEdit):
                            self.user_entry_fields[key].setPlainText(value['defaultValue'])
                            self.user_entry_fields[key].setReadOnly(True)
                        
                    elif 'valueList' in value:
                        print(f"[3] Setting requiredValue for key: {key} to {value['valueList']}")
                        if isinstance(self.user_entry_fields[key], QComboBox):
                            self.user_entry_fields[key].addItems(value['valueList'])
                        
                    else:
                        print(f"[4] Setting other value for key: {key} to {value}")
                        if isinstance(self.user_entry_fields[key], QLineEdit):
                            self.user_entry_fields[key].setText(str(value))
                            self.user_entry_fields[key].setReadOnly(True)
                        elif isinstance(self.user_entry_fields[key], QTextEdit):
                            self.user_entry_fields[key].setPlainText(str(value))    
                            self.user_entry_fields[key].setReadOnly(True)         
                        
        self.get_entered_text()
        
    def update_event_agent(self):
        self.current_value = self.user_entry_fields['Event-Agent'].currentText()
        self.bagger_info_dict['Event-Agent'] = self.current_value
        logging.debug(f"Event-Agent updated to: {self.current_value}")  # Debugging line
        
        print(f"Updated Event-Agent to: {self.current_value}")
        print(f"update JSON file dictionary: {self.bagger_info_dict}")
    
    
    def validate_registration_number(self):
        text = self.entry_file_name_registration_no_field.text()
        if text.isdigit() and len(text) == 3:
            # Continue with the rest of the script
            pass
        else:
        # Show warning message
            QMessageBox.warning(self, "Invalid Registration Number", f"The entered string '{text}' is not a valid registration number.\nIt must be a 3-digit number.")           
            
    def deselect_selected_items(self):
        # Deselect all selected drives
        print(f"Pre Selected Drives: {self.selected_drives_list}")
        self.selected_drives_list.clear()
        print(f"Post Selected Drives: {self.selected_drives_list}")
        self.selected_directories_list.clear()
        
        # Deselect all selected directories
        print(f"Pre Selected Directories: {self.selected_directories_list}")
        # self.update_selected_drives_text()
        print(f"Post Selected Directories: {self.selected_directories_list}")
        
        
        print(f"PRE formatted drive digital IDs: {self.formatted_drive_digital_ids_list}")
        self.formatted_drive_digital_ids_list.clear()
        print(f"POST formatted drive digital IDs: {self.formatted_drive_digital_ids_list}")
        
        # Define the Jinja2 selection template here
        self.template_str_selection = """
        
        <style>
            body {
                font-family: Consolas, monospace;  /* Use Consolas font, fallback to monospace */
            }
        </style>

        {% if drive_digital_ids or directory_digital_ids %}
            {% if drive_digital_ids %}
            <h3>Entered Digital IDs for Drive IDs:</h3>
            <ul>
                {% for digital_id in drive_digital_ids %}
                <li>{{ digital_id }}</li>
                {% endfor %}
            </ul>
            {% endif %}

            {% if directory_digital_ids %}
            <h3>Entered Digital IDs for Directories</h3>
            <ul>
                {% for digital_id in directory_digital_ids %}
                <li>{{ digital_id }}</li>
                {% endfor %}
            </ul>
            {% endif %}
        {% else %}
        <p>No digital IDs entered yet.</p>
        {% endif %}

        <h3>Selected Drives and Directories:</h3>
        {% if drives or directories %}
        <ul>
            {% if drives %}
            <h3>Drives:</h4>
            <ul>
                {% for drive in drives %}
                <li>{{ drive }}</li>
                {% endfor %}
            </ul>
            {% endif %}

            {% if directories %}
            <h3>Directories:</h4>
            <ul>
                {% for directory in directories %}
                <li>{{ directory }}</li>
                {% endfor %}
            </ul>
            {% endif %}
        </ul>
        {% else %}
        <p>No drives or directories selected yet.</p>
        {% endif %}
        """

        
    
    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        
        if directory:
            #Process of selecting a drive
            if os.path.ismount(directory):
                if directory not in self.selected_drives_list:
                    # self.media_numbers_drives_text = self.entry_file_name_media_no_drives_field.text()
                    directory = directory.rstrip('/\\')
                    self.selected_drives_list.append(directory)
                    print(f"This is a drive: {self.selected_drives_list }")
                    print(f"Drive path: {directory}")

                else:
                    QMessageBox.warning(self, "Warning", "Drive already selected.", QMessageBox.StandardButton.Ok)
                    
            #Process of selecting a directory         
            elif os.path.isdir(directory):
                if directory not in self.selected_directories_list:
                    self.selected_directories_list.append(directory)
                    print(f"This is a directory: {self.selected_directories_list }")
                else:
                    QMessageBox.warning(self, "Warning", "Directory already selected.", QMessageBox.StandardButton.Ok)
                    
        self.update_output_display()
        

        
    def check_for_comma(self):
        drive_text = self.entry_file_name_media_no_drives_field.text().strip()
        directory_text = self.entry_file_name_media_no_directories_field.text().strip()
        
        # Process drive media numbers
        if ',' in drive_text:
            parts = drive_text.split(',')
            numbers = parts[:-1]  # All except the last part are complete numbers
            for number in numbers:
                if number.isdigit():
                    digital_ID = self.bagger_info_dict["Id"] + "_" + self.entry_file_name_registration_no_field.text() + "_" + number
                    self.formatted_drive_digital_ids_list.append(digital_ID)
                    print(f"Drive digital ID: {self.formatted_drive_digital_ids_list}")
            # Keep the last incomplete part in the text field (after the last comma)
            self.entry_file_name_media_no_drives_field.setText(parts[-1])
            # self.update_display()

        # Process directory media numbers
        if ',' in  directory_text:
            parts =  directory_text.split(',')
            numbers = parts[:-1]  # All except the last part are complete numbers
            for number in numbers:
                if number.isdigit():
                    digital_ID = self.bagger_info_dict["Id"] + "_" + self.entry_file_name_registration_no_field.text() + "_" + number
                    self.formatted_directory_digital_ids_list.append(digital_ID)
                    print(f"Directory digital ID: {self.formatted_directory_digital_ids_list}")
            # Keep the last incomplete part in the text field (after the last comma)
            self.entry_file_name_media_no_directories_field.setText(parts[-1])
            # self.update_display()
            
    def space_enter_media_nos(self, collection_id, registration_no, drive_text, directory_text):
        # Process drive numbers
        drive_text = ' '.join(drive_text.split())
        directory_text = ' '.join(directory_text.split())
        
        # Split the drive text by spaces and process numbers
        drive_numbers = drive_text.split()
        for media_number in drive_numbers:
            if media_number.isdigit():
                digital_id = (
                    f"{collection_id}_{registration_no}_{media_number}"
                )

                if digital_id not in self.formatted_drive_digital_ids_list:
                    self.formatted_drive_digital_ids_list.append(digital_id)
                else:
                    QMessageBox.warning(
                        self,
                        "Duplicate Digital ID",
                        (
                            f"The digital ID {digital_id} has already "
                            "been entered for a drive."
                        ),
                        QMessageBox.StandardButton.Ok,
                    )

        # Clear the drive input field
        self.entry_file_name_media_no_drives_field.clear()

        # Split the directory text by spaces and process numbers
        directory_numbers = directory_text.split()
        for media_number in directory_numbers:
            if media_number.isdigit():
                digital_id = (
                    f"{collection_id}_{registration_no}_{media_number}"
                )

                if digital_id not in self.formatted_directory_digital_ids_list:
                    self.formatted_directory_digital_ids_list.append(
                        digital_id
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Duplicate Digital ID",
                        (
                            f"The digital ID {digital_id} has already "
                            "been entered for a directory."
                        ),
                        QMessageBox.StandardButton.Ok,
                    )

        # Clear the directory input field
        self.entry_file_name_media_no_directories_field.clear()

        # Pass the formatted lists to OutputManager for display
        self.update_output_display()

    def set_output_dir(self, state):
        if state == Qt.CheckState.Unchecked:
            self.clear_output_dir()
        # else:
        #     if self.checkbox_preserve_output.isChecked():
        #         self.preserve_output_dir()
                
    
    def select_output_directory(self):
         
        selected_directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if selected_directory and selected_directory != self.output_directory:
            self.output_directory = selected_directory
            print(f"Selected Output Directory: {self.output_directory}")

            # Update the display with the new directory
            self.update_output_display()

    def clear_output_dir(self):
        if 'output_directory' in self.output_dir_dictionary:
            del self.output_dir_dictionary['output_directory']
        print("Cleared output directory from dictionary")
            
    
    def build_inputs_map(self) -> dict[str, str]:
        """
        Return canonical mapping:
            digital_id -> absolute path
        """
        normalized = {}

        for path, digital_id in (
            self.selected_drives_digID_dictionary.items()
        ):
            absolute_path = os.path.abspath(path)

            if (
                os.name == "nt"
                and re.match(r"^[A-Za-z]:$", absolute_path)
            ):
                absolute_path += os.sep

            normalized[digital_id] = absolute_path

        for path, digital_id in (
            self.selected_directories_digID_dictionary.items()
        ):
            absolute_path = os.path.abspath(path)

            if (
                os.name == "nt"
                and re.match(r"^[A-Za-z]:$", absolute_path)
            ):
                absolute_path += os.sep

            normalized[digital_id] = absolute_path

        return normalized
        
# Function to run when the Run button is clicked and the selected is a drive

    def on_run_button_clicked(self ):

        

        menu_checkboxes = [ self.directory_checkbox, self.byte_count_checkbox, self.bagger_checkbox, self.directory_checkbox, self.special_file_exten_actio_checkbox, self.bagger_checkbox, self.excel_checkbox, self.html_checkbox, self.pdf_checkbox]
        
        if any(menu_selected.isChecked() for menu_selected in menu_checkboxes):
            print("At least one menu option is selected. Proceeding with the run.")
        else:
            QMessageBox.warning(
                self,
                "No Menu Option Selected",
                "Please select at least one menu option before running.",
                QMessageBox.StandardButton.Ok,
            )
            return  # Exit the function if no menu option is selected
        

        

        combined_dict = self.build_inputs_map()

        
        print("\n=== DEBUG: Inputs (digital_id -> path) ===")
        for did, path in combined_dict.items():
            print(f"Digital ID: {did}  →  Path: {path}")

        print("\n=== DEBUG: Selected Directories Dictionary ===")
        for path, did in self.selected_directories_digID_dictionary.items():
            print(f"Directory Path: {path} → Digital ID: {did}")

        print("\n=== DEBUG: Combined Dictionary (Drives + Directories) ===")
        for did, path in combined_dict.items():
            print(f"Digital ID: {did} → Path: {path}")

        print("=== END DEBUG ===\n")
        
        # --- Directory Listing ---
        if self.directory_checkbox.isChecked():
            if self.selected_drives_list or self.selected_directories_list:
                self.run_directory_listings()     
        if self.special_file_exten_actio_checkbox.isChecked():
            if self.selected_drives_list or self.selected_directories_list:
                self.directory_extension_scan()
                
        # # --- Bagger Listing ---
        if self.bagger_checkbox.isChecked():
            print("Running Bagger Listing...")
            self.run_bagger()
            # Add your actual Bagger Listing logic here
        # # --- Exiftool ---
        # if self.exiftool_checkbox.isChecked():
        #     print("Running Exiftool...")
        #     # Add your actual Exiftool logic here    
        # --- Byte Count ---
        if (
            self.byte_count_checkbox.isChecked()
            and not self.bagger_checkbox.isChecked()
        ):
            self.run_byte_count()
            
        reports_selected = (
            self.excel_checkbox.isChecked()
            or self.html_checkbox.isChecked()
            or self.pdf_checkbox.isChecked()
        )
        # Start reports immediately only when bagging is not selected.
        # When bagging is selected, _on_bagging_done() starts reports afterward.
        if reports_selected and not self.bagger_checkbox.isChecked():
            self.start_file_format_scan()
#Run Directory Command--Called when the run button is clicked; Apart of the on_run_button_clicked function    
## directory listings  
    def run_directory_listings(self):
        
        self.current_activity_label.setText(
            "Current Activity: Reading directory structure"
        )
        
        self.current_step_label.setText(
            "Current Step: Creating directory listing"
        )
        
        self.current_file_label.setText(
            "Current File: Scanning directory structure"
        )
        
        
        inputs_map = self.build_inputs_map()
        
        if inputs_map:
            first_source = next(iter(inputs_map.values()))
            self.current_source_label.setText(
                f"Current Source: {first_source}"
            )
        else:
            self.current_source_label.setText(
                "Current Source: None"
            )
        
        print("Running Directory Listings...")
        print(f"Input map for Directory Listing: {inputs_map}")


        if not inputs_map:
            self.output_manager.log_message(
                "⚠️ No drives or directories selected for directory listing."
            )
            self.reset_progress()
            return

        self.start_indeterminate_progress(
            "Running directory listing..."
        )

        for dig_id, path in inputs_map.items():
            self.output_manager.log_message(
                f"Starting Directory Listing: {dig_id} → {path}"
            )

        self.dir_worker = DirectoryListingWorker(
            inputs_map,
            self.output_directory,
            task_type="all",
        )

        self.dir_worker.progress_signal.connect(
            self.on_worker_message
        )

        self.dir_worker.completed_signal.connect(
            self.on_directory_listing_completed
        )

        self.dir_worker.start()
        

    def run_byte_count(self, inputs_map=None):
        if inputs_map is None:
            inputs_map = self.build_inputs_map()

        if not inputs_map:
            self.output_manager.log_message(
                "⚠️ No drives or directories selected for byte counting."
            )
            return

        if not self.output_directory:
            self.output_manager.log_message(
                "⚠️ Please select an output directory before byte counting."
            )
            return

        self.current_activity_label.setText(
            "Current Activity: Calculating byte counts"
        )
        # self.dir_worker.progress_signal.connect(
        #     self.output_text.append
        # )
        self.current_file_label.setText(
            "Current File: Preparing byte-count scan"
        )

        first_source = next(iter(inputs_map.values()))
        self.current_source_label.setText(
            f"Current Source: {first_source}"
        )

        self.output_manager.log_message(
            "Starting byte-count report..."
        )

        self.start_indeterminate_progress(
            "Calculating byte counts..."
        )

        self.byte_count_worker = ByteCountWorker(
            inputs_map=inputs_map,
            output_directory=self.output_directory,
            parent=self,
        )

        self.byte_count_worker.progress_signal.connect(
            self.output_manager.log_message
        )

        self.byte_count_worker.current_path_signal.connect(
            self._on_byte_count_current_path
        )

        self.byte_count_worker.error_signal.connect(
            self._on_byte_count_error
        )

        self.byte_count_worker.completed_signal.connect(
            self._on_byte_count_completed
        )

        self.byte_count_worker.start()


    def _on_byte_count_current_path(self, path):
        self.current_source_label.setText(
            f"Current Source: {path}"
        )

        self.current_file_label.setText(
            f"Current File: {os.path.basename(path) or path}"
        )


    def _on_byte_count_completed(self, results):
        report_path = results.get("report_path", "")
        processed = results.get("processed_objects", 0)
        matched = results.get("matched_bags", 0)
        mismatched = results.get("mismatched_bags", 0)
        unavailable = results.get("unavailable_oxum", 0)

        if report_path:
            self.output_manager.add_report_link(
                label="Byte Count Report — Excel",
                file_path=report_path
            )

        self.output_manager.log_message(
            "✅ Byte count completed. "
            f"Objects processed: {processed}; "
            f"Matching bags: {matched}; "
            f"Bag mismatches: {mismatched}; "
            f"Payload-Oxum unavailable: {unavailable}",
            level="SUCCESS"
        )

        if mismatched:
            self.finish_progress(
                "Byte count complete with mismatches"
            )
        else:
            self.finish_progress("Byte count complete")

        self.current_activity_label.setText(
            "Current Activity: Byte count complete"
        )
        self.current_step_label.setText(
            "Current Step: Excel report created"
        )
        self.current_file_label.setText(
            "Current File: None"
        )
        self.current_source_label.setText(
            "Current Source: None"
        )

        reports_selected = (
            self.excel_checkbox.isChecked()
            or self.html_checkbox.isChecked()
            or self.pdf_checkbox.isChecked()
        )

        if reports_selected and self.bagger_checkbox.isChecked():
            self.start_file_format_scan()

    def _on_byte_count_error(self, message):
        self.output_manager.log_message(
            f"Byte count failed: {message}",
            level="ERROR"
        )

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Byte count failed")

        self.current_activity_label.setText(
            "Current Activity: Byte count failed"
        )
        self.current_step_label.setText(
            "Current Step: Error"
        )
    
    def on_directory_listing_completed(self, results):
        self.current_step_label.setText(
            "Current Step: Directory listing complete"
        )

        self.current_file_label.setText(
            "Current File: None"
        )
        
        self.output_manager.log_message(
            "Drive Directory Listings Completed!"
        )

        for kind, path in results.items():
            self.output_manager.add_report_link(
                label=f"Directory Listing — {kind.upper()}",
                file_path=path
            )
            
        self.current_activity_label.setText(
            "Current Activity: Directory listing complete"
        )

        self.current_source_label.setText(
            "Current Source: None"
        )

        self.update_output_display()
        self.finish_progress("Directory listing complete")

    def on_drive_listings_completed(self, results):
        self.output_manager.log_message("Drive Directory Listings Completed!")

        for kind, path in results.items():
            self.output_manager.add_report_link(
                label=f"Directory Listing — {kind.upper()}",
                file_path=path
            )

        self.update_output_display()
        self.finish_progress("Directory listing complete")           
            
    def job_competed(self):
        self.run_button_color = "red"
        self.run_program_button.setStyleSheet("background-color: red;")
        self.completed_directory_drive()


        
   ## End of the script to create directory listings     
   ## Start of scripts to scan for specific file extensions
   
    def directory_extension_scan(self):
        self.current_activity_label.setText(
            "Current Activity: Searching for known file extensions"
        )
        inputs_map = self.build_inputs_map()
        print(f"Extension Scan Inputs: {inputs_map}")
        
        if inputs_map:
            first_path = next(iter(inputs_map.values()))
            self.current_source_label.setText(
                f"Current Source: {first_path}"
            )
        else:
            self.current_source_label.setText(
                "Current Source: None"
            )
                

        if not inputs_map:
            self.output_manager.log_message(
                "⚠️ No drives or directories selected "
                "for file extension scan."
            )
            self.reset_progress()
            return

        self.start_indeterminate_progress(
            "Scanning file extensions..."
        )

        for dig_id, path in inputs_map.items():
            self.output_manager.log_message(
                f"Starting file extension scan: {dig_id} → {path}"
            )

        self.current_step_label.setText(
            "Current Step: Scanning file extensions"
        )

        self.current_file_label.setText(
            "Current File: Discovering file types"
        )

        self.file_extension_worker = FileExtensionScanWorker(
            inputs_map,
            self.output_directory,
            task_type="both",
        )

        self.file_extension_worker.progress_signal.connect(
            self.on_worker_message
        )

        self.file_extension_worker.completed_signal.connect(
            self.on_extension_scan_completed
        )
        

        self.file_extension_worker.start()
        
        
    def on_extension_scan_completed(self, results):

        self.output_manager.log_message("File extension scan completed!")

        for kind, path in results.items():
            self.output_manager.add_report_link(
                label=f"File extension scan — {kind.upper()}",
                file_path=path
            )

        self.current_step_label.setText(
            "Current Step: File extension scan complete"
        )

        
        self.current_activity_label.setText(
            "Current Activity: File extension scan complete"
        )

        self.current_source_label.setText(
            "Current Source: None"
        )

        self.finish_progress("File extension scan complete")
            
    def completed_directory_drive(self):
        self.completed_dir_drives.update(self.selected_directories_digID_dictionary)
        # self.selected_directories_digID_dictionary.clear()
        print(f"completed dictionary: {self.completed_dir_drives}")
    
        
    def get_entered_text(self):
        for field_key, widget in self.user_entry_fields.items():
            if isinstance(widget, QLineEdit):
                self.bagger_info_dict[field_key] = widget.text()
                print(f"{field_key}: {widget.text()}")
            elif isinstance(widget, QTextEdit):
                self.bagger_info_dict[field_key] = widget.toPlainText()
                print(f"{field_key}: {widget.toPlainText()}")
            elif isinstance(widget, QComboBox):
                self.bagger_info_dict[field_key] = widget.currentText()
                print(f"{field_key}: {widget.currentText()}")
        print(f"dictionary: {self.bagger_info_dict}")
        print(f'collection ID: {self.bagger_info_dict["Id"]}')
  
        
    def confirm_directories_path_IDs(self):
    # Drives
        count_digital_id_drives = len(self.formatted_drive_digital_ids_list)
        count_select_path_drives = len(self.selected_drives_list)
        
        # Directories
        count_digital_id_directories = len(self.formatted_directory_digital_ids_list)
        count_select_path_directories = len(self.selected_directories_list)
        
        # Drive Mismatch check and error
        if count_digital_id_drives != count_select_path_drives:
            QMessageBox.warning(self, "Mismatch Error", 
            f"The number of entered media numbers: <b>{count_digital_id_drives} </b>does not match the number of selected Drives: <b>{count_select_path_drives}</b>", 
            QMessageBox.StandardButton.Ok)
            
            
        elif count_select_path_drives > 0:
            self.selected_drives_digID_dictionary = {
                drive: digital_id
                for drive, digital_id in zip(
                    self.selected_drives_list,
                    self.formatted_drive_digital_ids_list
                )
            }

            print(
                "Completed Pairing of selected drives and Digital IDs: "
                f"{self.selected_drives_digID_dictionary}"
            )


        if count_digital_id_directories != count_select_path_directories:
            QMessageBox.warning(
                self,
                "Mismatch Error",
                (
                    f"The number of entered media numbers: "
                    f"<b>{count_digital_id_directories}</b> "
                    f"does not match the number of selected directories: "
                    f"<b>{count_select_path_directories}</b>"
                ),
                QMessageBox.StandardButton.Ok
            )

        elif count_select_path_directories > 0:
            self.selected_directories_digID_dictionary = {
                directory: digital_id
                for directory, digital_id in zip(
                    self.selected_directories_list,
                    self.formatted_directory_digital_ids_list
                )
            }

            print(
                "Completed Pairing of selected directories and Digital IDs: "
                f"{self.selected_directories_digID_dictionary}"
            )   
        
    # Pass the dictionaries to update_display_confirm
        self.update_output_display()

    # Function to run the file format scan


        
# Functions for running file format checks
    def run_dir_file_format(self):
        
        for key, value in self.selected_directories_digID_dictionary.items():

            directory_file_format_output = os.path.join(self.output_directory, "Reports", "File_Format_Output")
            print(f'output location: {self.output_directory}')
            print(f"directory listing output: {directory_file_format_output}")
            if not os.path.exists(directory_file_format_output):
                os.makedirs(directory_file_format_output)
            else:
                pass

    
    def start_file_format_scan(self):
        self.output_manager.file_format_links.clear()
        self.update_output_display()
        self.current_activity_label.setText(
            "Current Activity: Running Siegfried"
        )
        # Collect UI state, build inputs_map (digital_id->path), and launch the worker.
        base_output_dir = getattr(self, "output_directory", None)
        if not base_output_dir:
            QMessageBox.warning(self, "Missing Output", "Please select an output directory first.")
            return

        inputs_map = self.build_inputs_map()

        if not inputs_map:
            QMessageBox.warning(self, "No Inputs", "Confirm Digital IDs for selected drives/directories first.")
            return
        self.start_indeterminate_progress("Scanning file formats...")
                # Output flags from checkboxes (HTML / PDF / EXCEL only)
        do_html  = bool(self.html_checkbox.isChecked())
        do_pdf   = bool(self.pdf_checkbox.isChecked())
        do_excel = bool(self.excel_checkbox.isChecked())
        # Bagger info (optional)
        bagger_info = getattr(self, "bagger_info_dict", {}) or {}
        
        # Thread + Worker
        self.filefmt_thread = QThread(self)
        self.filefmt_worker = FileFormatScanWorker(
            base_output_dir=base_output_dir,
            inputs_map=inputs_map,
            bagger_info=bagger_info,
            do_html=do_html,
            do_pdf=do_pdf,
            do_excel=do_excel,
            do_csv=False,  # explicitly off
        )
        self.filefmt_worker.moveToThread(self.filefmt_thread)
        
        # Signals
        self.filefmt_thread.started.connect(self.filefmt_worker.run)
        self.filefmt_worker.progress.connect(self.on_filefmt_progress)
        self.filefmt_worker.finished.connect(self.on_filefmt_finished)
        self.filefmt_worker.error.connect(self.on_filefmt_error)
        
        # Cleanup
        self.filefmt_worker.finished.connect(self.filefmt_thread.quit)
        self.filefmt_worker.finished.connect(self.filefmt_worker.deleteLater)
        self.filefmt_thread.finished.connect(self.filefmt_thread.deleteLater)

        # UI busy state
        self._set_busy(True)
        self.filefmt_thread.finished.connect(lambda: self._set_busy(False))

        self.filefmt_thread.start()
        
    def _set_busy(self, busy: bool):
        
        for w in [getattr(self, "run_program_button", None),
                getattr(self, "html_checkbox", None),
                getattr(self, "pdf_checkbox", None),
                getattr(self, "excel_checkbox", None)]:
            
                if w:
                    w.setEnabled(not busy)
        try:
            self.statusBar().showMessage("Running…" if busy else "Ready")
            
        except Exception:
            pass  
            
    def on_filefmt_finished(self, created: dict):
        
        self.current_step_label.setText(
            "Current Step: File-format processing complete"
        )

        self.current_activity_label.setText(
            "Current Activity: Complete"
        )

        self.current_file_label.setText(
            "Current File: None"
        )

        self.current_source_label.setText(
            "Current Source: None"
        )
        
        self.finish_progress("File-format scan complete")

        if not created:
            QMessageBox.information(
                self,
                "File Format Scan",
                "No files were created."
            )
            return

        for kind, path in created.items():
            self.output_manager.add_report_link(
                label=f"File Format Report — {kind.upper()}",
                file_path=path
            )

        QMessageBox.information(
            self,
            "File Format Scan",
            "Outputs created. See the log for links."
        )
            
    def on_filefmt_progress(self, msg: str):
        self.output_manager.log_message(msg)
        self.logger.info(msg)
        message_lower = msg.lower()    
        
        if "scanning files with siegfried" in message_lower:
            self.current_step_label.setText(
                "Current Step: File format identification"
            )    
            self.current_activity_label.setText(
                "Current Activity: Running Siegfried"
            )
            
        elif "scan complete" in message_lower:
            self.current_activity_label.setText(
                "Current Activity: File identification complete"
            )
            
        elif "merging results" in message_lower:
            self.current_step_label.setText(
                "Current Step: Preparing reports"
            )
            self.current_activity_label.setText(
                "Current Activity: Merging scan results"
            )
        elif "preparing render data" in message_lower:
            self.current_activity_label.setText(
                "Current Activity: Preparing report data"
            )
        elif "generating outputs" in message_lower:
            self.current_step_label.setText(
                "Current Step: Generating reports"
            )
            self.current_activity_label.setText(
                "Current Activity: Generating selected reports"
            )   
            
        elif "generating html report" in message_lower:
            self.current_step_label.setText(
                "Current Step: Generating reports"
            )
            self.current_activity_label.setText(
                "Current Activity: Generating HTML report"
            )

        elif "html report created" in message_lower:
            self.current_activity_label.setText(
                "Current Activity: HTML report created"
            )

        elif "generating pdf report" in message_lower:
            self.current_step_label.setText(
                "Current Step: Generating reports"
            )
            self.current_activity_label.setText(
                "Current Activity: Generating PDF report"
            )

        elif "pdf report created" in message_lower:
            self.current_activity_label.setText(
                "Current Activity: PDF report created"
            )

        elif "generating excel report" in message_lower:
            self.current_step_label.setText(
                "Current Step: Generating reports"
            )
            self.current_activity_label.setText(
                "Current Activity: Generating Excel report"
            )

        elif "excel report created" in message_lower:
            self.current_activity_label.setText(
                "Current Activity: Excel report created"
            )    
            
            
            
    def on_filefmt_error(self, message: str):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("File-format scan failed")
        QMessageBox.critical(self, "File Format Scan Error", message)
        self.output_manager.log_message(
            f"File format scan failed: {message}",
            level="ERROR"
        )
        self.logger.error("File format scan failed: %s", message)
            
        self.current_step_label.setText(
            "Current Step: File-format processing error"
        )

        self.current_activity_label.setText(
            "Current Activity: Processing failed"
        )

        self.current_file_label.setText(
            "Current File: See error details"
        )
        
        self.current_source_label.setText(
            "Current Source: None"
        )

    
    def run_bagger(self):

        """
        Start the BaggingWorker using a digital_id -> path mapping.

        Keeps debug prints so we can confirm:
        - output directory value
        - raw_map direction coming from build_inputs_map()
        - final inputs_map direction passed to the worker
        """
        import os
        from pathlib import Path

        print("\n=== BAGGER DEBUG (run_bagger) ===")
        print("DEBUG main_window.py path:", os.path.abspath(__file__))
        print("DEBUG cwd:", os.getcwd())
        print("output_directory var:", getattr(self, "output_directory", None))
        print("selected_output_directory var:", getattr(self, "selected_output_directory", None))

        raw_map = self.build_inputs_map()
        self.logger.debug("raw_map type: %s", type(raw_map).__name__)
        self.logger.debug("raw_map length: %d", len(raw_map))
        self.logger.debug(
            "raw_map preview: %s",
            list(raw_map.items())[:3]
        )
        
        self.current_activity_label.setText(
            "Current Activity: Copying files into BagIt structure"
        )
        
        

        # Determine if raw_map is path->did or did->path
        inputs_map = {}
        if raw_map:
            k, v = next(iter(raw_map.items()))
            key_looks_like_path = (":" in str(k)) or str(k).startswith(("/", "\\"))
            val_looks_like_path = (":" in str(v)) or str(v).startswith(("/", "\\"))

            print("raw_map first key:", k)
            print("raw_map first val:", v)
            print("key looks like drive/path?:", key_looks_like_path)
            print("val looks like drive/path?:", val_looks_like_path)

            if key_looks_like_path and not val_looks_like_path:
                # raw_map is path -> digital_id, flip it for bagger
                inputs_map = {did: path for path, did in raw_map.items()}
                print("Detected raw_map direction: path -> digital_id (flipping for bagger)")
            else:
                # raw_map is already digital_id -> path
                inputs_map = dict(raw_map)
                print("Detected raw_map direction: digital_id -> path (no flip needed)")

        print("inputs_map (to worker) len:", len(inputs_map))
        print("inputs_map preview:", list(inputs_map.items())[:3])
        print("=== END BAGGER DEBUG ===\n")

        if not inputs_map:
            self.output_manager.log_message("⚠️ No drives or directories selected for bagging.")
            return

        if not getattr(self, "output_directory", None):
            self.output_manager.log_message("⚠️ Please select an output directory first.")
            return

        # If you already import BaggingWorker at module level, you can remove this import.
        from workers.bagger_worker import BaggingWorker

        print("Creating BaggingWorker with output_directory:", self.output_directory)

        self.bag_worker = BaggingWorker(
            inputs_map=inputs_map,
            output_directory=Path(self.output_directory),
            bagger_info_dict=self.bagger_info_dict,
            profile_path=(
                Path(self.bagger_profile_file_path)
                if hasattr(self, "bagger_profile_file_path")
                else None
            ),
        )

        self.bag_worker.progress_signal.connect(
            self.on_worker_message
        )

        self.bag_worker.progress_percent_signal.connect(
            self.update_progress
        )

        self.bag_worker.file_started_signal.connect(
            self._on_bag_file_started
        )

        self.bag_worker.file_completed_signal.connect(
            self._on_bag_file_completed
        )

        self.bag_worker.error_signal.connect(
            self._on_bagging_error
        )

        self.bag_worker.completed_signal.connect(
            self._on_bagging_done
        )
        self.bag_worker.start()
        
    def on_worker_message(self, message):
        """Handle worker messages consistently."""

        message = str(message).strip()

        if not message:
            return

        lower = message.lower()

        # Ignore repetitive file-copying messages.
        if (
            lower.startswith(("copying:", "copied:"))
            or lower.startswith(("▶ copying:", "✅ copied:"))
        ):
            return

        if "error" in lower or "failed" in lower:
            level = "ERROR"
        elif "warning" in lower:
            level = "WARNING"
        elif "completed" in lower or "successfully" in lower:
            level = "SUCCESS"
        else:
            level = "INFO"

        self.output_manager.log_message(
            message,
            level=level
        )
        
    
        
    def _on_bag_file_started(
        self,
        digital_id: str,
        source_path: str,
        current: int,
        total: int,
    ):
        filename = Path(source_path).name
        
        self.current_step_label.setText(
            f"Current Step: Copying files ({current} of {total})"
        )
        
        self.current_activity_label.setText(
            f"Current Activity: Copying file {current} of {total}"
        )

        self.current_file_label.setText(
            f"Current File: {filename}"
        )

        self.current_source_label.setText(
            f"Current Source: {source_path}"
        )



    def _on_bag_file_completed(
        self,
        digital_id,
        source_path,
        current,
        total
    ):
        filename = Path(source_path).name
        
        self.current_step_label.setText(
            f"Current Step: Finished file ({current} of {total})"
        )
        
        self.current_activity_label.setText(
            f"Current Activity: Copied file {current} of {total}"
        )

        self.current_file_label.setText(
            f"Current File: {filename}"
        )

        self.current_source_label.setText(
            f"Current Source: {source_path}"
        )   
                    
    
    def _on_bagging_done(self, summary: dict):
        results = summary.get("results", {})
        had_errors = summary.get("had_errors", False)
        failures = summary.get("failures", [])

        for digital_id, bag_path in results.items():
            self.output_manager.log_message(
                f"✅ Bag created: {digital_id} → {bag_path}"
            )

        if had_errors:
            self.output_manager.log_message(
                f"Bagging completed with errors. "
                f"Successful bags: {len(results)}; "
                f"Failed bags: {len(failures)}",
                level="WARNING"
            )

            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat(
                "Completed with errors"
            )

            self.current_step_label.setText(
                "Current Step: Bagging completed with errors"
            )
            
            self.current_activity_label.setText(
                "Current Activity: Bagging finished with errors"
            )
            
            self.current_file_label.setText(
                "Current File: None"
            )
            self.current_source_label.setText(
                "Current Source: None"
            )
        else:
            self.output_manager.log_message(
                "🎉 Bagging completed successfully."
            )

            self.finish_progress("Bagging complete")

            self.current_step_label.setText(
                "Current Step: Bagging complete"
            )
            
            self.current_activity_label.setText(
                "Current Activity: Bagging complete"
            )
                
            self.current_file_label.setText(
                "Current File: None"
            )
            
            self.current_source_label.setText(
                "Current Source: None"
            )
            

        reports_selected = (
            self.excel_checkbox.isChecked()
            or self.html_checkbox.isChecked()
            or self.pdf_checkbox.isChecked()
        )

        if self.byte_count_checkbox.isChecked() and results:
            self.run_byte_count(inputs_map=results)
            
        elif reports_selected:
            self.start_file_format_scan()
        
    def _on_bagging_error(self, message: str):
        
        self.output_manager.log_message(
            f"Bagging failed: {message}",
            level="ERROR"
        )
        self.logger.error(message)

        self.current_step_label.setText("Current Step: Bagging error")
        self.current_file_label.setText("Current File: See error details")

        self.logger.error(message)

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Bagging failed")
                   

    def reset_state(self):
        """Clear all selections, digital IDs, and dictionaries from memory."""

        # Clear drives
        self.selected_drives_list.clear()
        self.formatted_drive_digital_ids_list.clear()
        self.media_numbers_drive_list.clear()
        self.selected_drives_digID_dictionary.clear()

        # Clear directories
        self.selected_directories_list.clear()
        self.formatted_directory_digital_ids_list.clear()
        self.media_numbers_directories_list.clear()
        self.selected_directories_digID_dictionary.clear()

        # Clear completed runs
        self.completed_dir_drives.clear()

        # Reset labels
        self.selected_directory_label.clear()
        self.selected_drive_label.clear()

        # Reset GUI inputs
        self.entry_file_name_media_no_directories_field.clear()
        self.entry_file_name_media_no_drives_field.clear()
        self.entry_file_name_registration_no_field.clear()

        # Reset run button color
        self.run_button_color = "gray"
        self.run_program_button.setStyleSheet("")
        
        self.current_step_label.setText(
            "Current Step: Ready"
        )

        self.current_file_label.setText(
            "Current File: None"
        )

        self.current_source_label.setText(
            "Current Source: None"
        )

        self.current_activity_label.setText(
            "Current Activity: Ready"
        )
        
        if not self.checkbox_preserve_output.isChecked():
            self.output_directory = ""

        # Update display
        self.update_output_display()
        
        # Reset progress bar
        self.reset_progress()

    print("✅ All selections and state have been reset.")

    
    def extract_media_number(self, digital_id):
            # Split the digital ID by underscores
        parts = digital_id.split('_')
        # The media number is the last part of the split string
        media_number = parts[-1]
        return media_number
    
    
    def remove_media_number_from_list(
        self,
        digital_id,
        media_number_list,
    ):
        """
        Remove the final media-number portion of a digital ID from a
        corresponding media-number list.
        """

        media_number = self.extract_media_number(digital_id)

        while media_number in media_number_list:
            media_number_list.remove(media_number)


    def rebuild_selection_dictionaries(self):
        """
        Rebuild path-to-digital-ID dictionaries from the current ordered
        lists.

        This prevents stale pairings after a path or digital ID is removed.
        """

        self.selected_drives_digID_dictionary = {
            drive: digital_id
            for drive, digital_id in zip(
                self.selected_drives_list,
                self.formatted_drive_digital_ids_list,
            )
        }

        self.selected_directories_digID_dictionary = {
            directory: digital_id
            for directory, digital_id in zip(
                self.selected_directories_list,
                self.formatted_directory_digital_ids_list,
            )
        }
        
    
    def deselect_items(self):  
        """
        Allow the user to remove selected drives, selected directories,
        or unpaired digital IDs.

        A digital ID can be removed even when no drive or directory was
        successfully selected.
        """

        deselect_dialog = DeselectDialog(
            self.selected_drives_list,
            self.selected_directories_list,
            self.formatted_drive_digital_ids_list,
            self.formatted_directory_digital_ids_list,
            parent=self,
        )

        if deselect_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        (
            selected_drives,
            selected_directories,
            selected_drive_digital_ids,
            selected_directory_digital_ids,
        ) = deselect_dialog.get_selected_items()

        # Remove selected drives.
        for drive in selected_drives:
            if drive in self.selected_drives_list:
                self.selected_drives_list.remove(drive)

            # Remove an existing drive-to-ID pairing, if one exists.
            paired_digital_id = self.selected_drives_digID_dictionary.pop(
                drive,
                None,
            )

            if (
                paired_digital_id
                and paired_digital_id in self.formatted_drive_digital_ids_list
            ):
                self.formatted_drive_digital_ids_list.remove(
                    paired_digital_id
                )

                self.remove_media_number_from_list(
                    paired_digital_id,
                    self.media_numbers_drive_list,
                )

        # Remove selected directories.
        for directory in selected_directories:
            if directory in self.selected_directories_list:
                self.selected_directories_list.remove(directory)

            # Remove an existing directory-to-ID pairing, if one exists.
            paired_digital_id = (
                self.selected_directories_digID_dictionary.pop(
                    directory,
                    None,
                )
            )

            if (
                paired_digital_id
                and paired_digital_id
                in self.formatted_directory_digital_ids_list
            ):
                self.formatted_directory_digital_ids_list.remove(
                    paired_digital_id
                )

                self.remove_media_number_from_list(
                    paired_digital_id,
                    self.media_numbers_directories_list,
                )

        # Remove drive IDs independently of selected drive paths.
        for digital_id in selected_drive_digital_ids:
            if digital_id in self.formatted_drive_digital_ids_list:
                self.formatted_drive_digital_ids_list.remove(digital_id)

            self.remove_media_number_from_list(
                digital_id,
                self.media_numbers_drive_list,
            )

            # Remove any pairing that uses this ID.
            paths_to_remove = [
                path
                for path, paired_id
                in self.selected_drives_digID_dictionary.items()
                if paired_id == digital_id
            ]

            for path in paths_to_remove:
                self.selected_drives_digID_dictionary.pop(path, None)

        # Remove directory IDs independently of selected directory paths.
        for digital_id in selected_directory_digital_ids:
            if digital_id in self.formatted_directory_digital_ids_list:
                self.formatted_directory_digital_ids_list.remove(
                    digital_id
                )

            self.remove_media_number_from_list(
                digital_id,
                self.media_numbers_directories_list,
            )

            # Remove any pairing that uses this ID.
            paths_to_remove = [
                path
                for path, paired_id
                in self.selected_directories_digID_dictionary.items()
                if paired_id == digital_id
            ]

            for path in paths_to_remove:
                self.selected_directories_digID_dictionary.pop(
                    path,
                    None,
                )

        # Rebuild pairings so list positions remain synchronized.
        self.rebuild_selection_dictionaries()

        self.update_output_display()
    
    def show_user_guide(self):
        """Display the User Guide."""

        dialog = HelpDialog(
            html_path=HELP_DOCS_DIR / "user_guide.html",
            title="User Guide",
            parent=self,
        )
        dialog.exec()
    
    def get_recent_log_lines(self, line_count=75):
        """Return the most recent lines from the application log."""

        log_file = (
            Path.home()
            / ".BornDigitalProcessing"
            / "logs"
            / "born_digital_processing.log"
        )

        try:
            with log_file.open(
                "r",
                encoding="utf-8",
                errors="replace",
            ) as file:
                recent_lines = deque(file, maxlen=line_count)

            return "".join(recent_lines)

        except OSError as exc:
            return f"Unable to read log file: {exc}"


    def show_report_issue_help(self):
        """Open the bug and suggestion report dialog."""

        log_excerpt = self.get_recent_log_lines(
            line_count=150
        )

        dialog = FeedbackDialog(
            log_excerpt=log_excerpt,
            parent=self,
        )

        dialog.exec()
        
    def show_about(self):
        try:
            bagit_version = version("bagit")
        except PackageNotFoundError:
            bagit_version = "Not installed"

        project_root = Path(__file__).resolve().parent.parent

        about_path = (
            project_root
            / "core"
            / "help_docs"
            / "about.html"
        )
        version_path = (
            project_root
            / "core"
            / "version.json"
        )
        
        try:
            with version_path.open("r", encoding="utf-8") as version_file:
                version_info = json.load(version_file)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            version_info = {
                "version": "Unknown",
                "build": "Unknown",
                "build_date": "Unknown",
                "status": "Unknown",
            }
        
        dialog = HelpDialog(
            html_path=about_path,
            title="About",
            replacements={
                "BAGIT_VERSION": bagit_version,
                "version": version_info.get("version", "Unknown"),
                "build": version_info.get("build", "Unknown"),
                "build_date": version_info.get("build_date", "Unknown"),
                "status": version_info.get("status", "Unknown"),
            },
            parent=self,
        )

        dialog.exec()
        
                
    def start_flask_server(self):
        # Check if server is already running
        
        try:
            with socket.create_connection(("127.0.0.1", 5000), timeout=1):
                print("Flask server is already running.")
            return

        except (ConnectionRefusedError, TimeoutError, OSError):
            #Server not running, so start it
            server_path = os.path.join(os.path.dirname(__file__), "open_file_server.py")
            subprocess.Popen([sys.executable, server_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        
        
        # try:
        #     # Try to connect to the server
        #     import socket
        #     sock = socket.create_connection(("localhost", 5000), timeout=2)
        #     sock.close()
        # except (ConnectionRefusedError, OSError):
        #     # Server not running, so start it
        #     server_path = os.path.join(os.path.dirname(__file__), "open_file_server.py")
        #     subprocess.Popen([sys.executable, server_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


