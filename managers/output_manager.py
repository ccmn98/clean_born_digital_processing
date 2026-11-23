from jinja2  import Template
import subprocess
import os
from datetime import datetime
import logging
from pathlib import Path
logger = logging.getLogger(__name__)

class OutputManager:
    def __init__(self, output_widget, html_file_path="output.html", parent=None):
        self.output_widget = output_widget
        self.html_file_path = html_file_path
        self.file_created = False
        self.output_logs = []
        self.file_format_links = []
        self.report_links = []
        self.parent_app = parent  # Store the DirOutputApp instance
        
        # Track sections separately
        self.output_directory_section = ""
        self.selection_section = ""
        self.confirmation_section = ""
        
        # Define the Jinja2 template
        self.combined_template_str = """
        <style>
            body {
                font-family: Consolas, monospace;
            }
            .log {
                color: green;
            }
            
            .processing-log {
            font-family: Consolas, monospace;
            font-size: 12px;
            line-height: 1.5;
        }

        .log-entry {
            display: flex;
            align-items: baseline;
            gap: 8px;
            padding: 4px 6px;
            border-bottom: 1px solid #e5e5e5;
        }

        .log-time {
            flex: 0 0 65px;
            color: #777;
        }

        .log-icon {
            flex: 0 0 16px;
            font-weight: bold;
        }

        .log-message {
            flex: 1;
            overflow-wrap: anywhere;
        }

        .log-info {
            color: #2463a6;
        }

        .log-success {
            color: #16803c;
        }

        .log-warning {
            color: #a36a00;
        }

        .log-error,
        .log-critical {
            color: #b42318;
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
            <h3>Entered Digital IDs for Directories:</h3>
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
            <h4>Drives:</h4>
            <ul>
                {% for drive in drives %}
                <li>{{ drive }}</li>
                {% endfor %}
            </ul>
            {% endif %}
            {% if directories %}
            <h4>Directories:</h4>
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

        {% if output_directory %}
        <h3>Selected Output Directory:</h3>
        <ul>
            <li><b>{{ output_directory }}</b></li>
        </ul>
        {% endif %}

        {% if confirm_drives or confirm_directories %}
        <h3>Confirmation of Digital ID Pairings:</h3>
        {% if confirm_drives %}
        <ul>
            <h4>Drives and Digital IDs:</h4>
            <ul>
                {% for drive, digital_id in confirm_drives.items() %}
                <li><b>{{ digital_id }}</b> : {{ drive }}</li>
                {% endfor %}
            </ul>
        </ul>
        {% endif %}
        {% if confirm_directories %}
        <ul>
            <h4>Directories and Digital IDs:</h4>
            <ul>
                {% for directory, digital_id in confirm_directories.items() %}
                <li><b>{{ digital_id }}</b> : {{ directory }}</li>
                {% endfor %}
            </ul>
        </ul>
        {% endif %}
        {% endif %}

        <!-- New section for logs -->
        <h3>Processing Logs:</h3>

        {% if logs %}
        <table class="processing-log" cellspacing="0" cellpadding="4">
            {% for log in logs %}
            <tr>
                <td width="65" valign="top">
                    <span style="color:#777;">
                        {{ log.timestamp }}
                    </span>
                </td>
                <td width="20" valign="top">
                    {{ log.icon }}
                </td>
                <td valign="top">
                    <span class="log-{{ log.level | lower }}">
                        {{ log.message | e }}
                    </span>
                </td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <p>No processing messages yet.</p>
        {% endif %}
                
        {% if report_links %}
            <h3>Generated Reports:</h3>
            <ul>
                {% for report in report_links %}
                    <li>
                        <a href="{{ report.url | e }}">
                            {{ report.label | e }}
                        </a>
                    </li>
                {% endfor %}
            </ul>
        {% endif %}
        {% if file_format_links %}
        <h3>File Format Reports:</h3>
        <div class="file-format-links">
            <ul>
                {% for link in file_format_links %}
                    <li>{{ link | safe }}</li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}

        """
        self.combined_template = Template(self.combined_template_str)

    def open_file_in_notepad(self, file_path):
        """Open the given file in Notepad."""
        try:
            subprocess.Popen(["notepad.exe", file_path], shell=True)
        except Exception as e:
            logger.exception("Failed to open file in Notepad")

    def append_content(self, content):
        current_content = self.output_widget.toHtml()
        logger.debug(
            "Appending HTML content (%d characters)",
            len(content)
        )
        self.output_widget.setHtml(current_content + content)

    def clear_output(self):
        self.output_widget.clear()

    def save_to_html_file(self, html_content):
        # Check if file exists before appending for the first time
        if not self.file_created:
            # Create and open the file in write mode to ensure it exists
            with open(self.html_file_path, "w") as file:
                file.write("")  # Write empty content initially
            logger.debug(
                "HTML output file created: %s",
                os.path.abspath(self.html_file_path)
            )
            self.file_created = True  # Mark file as created
            
        # Now append the new content
        with open(self.html_file_path, "w") as file:
            file.write(html_content)
    
    def update_display(self, selected_drives_list, selected_directories_list, drive_digital_ids_list, directory_digital_ids_list, output_directory, confirm_drives=None, confirm_directories=None):
        # Render combined HTML content
        data = {
            "drives": selected_drives_list,
            "directories": selected_directories_list,
            "drive_digital_ids": drive_digital_ids_list,
            "directory_digital_ids": directory_digital_ids_list,
            "output_directory": output_directory,
            "confirm_drives": confirm_drives,
            "confirm_directories": confirm_directories,
            "logs": self.output_logs,
            "file_format_links": self.file_format_links,
            "report_links": self.report_links,
        }
        full_content = self.combined_template.render(data)
        
        # Update file and display without overwriting other sections
        self.update_full_display(full_content)
        
        
    def update_full_display(self, full_content):
        """Save HTML output and refresh the GUI."""

        with open(
            self.html_file_path,
            "w",
            encoding="utf-8"
        ) as file:
            file.write(full_content)

        self.output_widget.setHtml(full_content)
 
        
    def load_html_to_output(self):
        # Read HTML content and display in the output widget
        with open(self.html_file_path, "r", encoding="utf-8") as file:
            content = file.read()
        self.output_widget.setHtml(content)
        
    def log_message(self, message, level="INFO", **_):
        level = level.upper()

        if level == "DEBUG":
            return

        icons = {
            "INFO": "ℹ",
            "SUCCESS": "✓",
            "WARNING": "⚠",
            "ERROR": "✗",
            "CRITICAL": "✗",
        }

        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "icon": icons.get(level, "ℹ"),
            "message": str(message),
        }

        # Prevent identical consecutive messages
        if self.output_logs:
            previous = self.output_logs[-1]

            if (
                previous["message"] == entry["message"]
                and previous["level"] == entry["level"]
            ):
                return
        self.output_logs.append(entry)
        
        self.update_display(
            self.parent_app.selected_drives_list,
            self.parent_app.selected_directories_list,
            self.parent_app.formatted_drive_digital_ids_list,
            self.parent_app.formatted_directory_digital_ids_list,
            self.parent_app.output_directory,
            self.parent_app.selected_drives_digID_dictionary,
            self.parent_app.selected_directories_digID_dictionary,
        )
        

    def add_report_link(self, label, file_path):
        """Register a report link for display."""

        path = Path(file_path).resolve()

        if not path.is_file():
            logging.getLogger(__name__).warning(
                "Report file does not exist: %s", path
            )
            return

        entry = {
            "label": str(label),
            "url": path.as_uri(),
        }

        if entry not in self.report_links:
            self.report_links.append(entry)

            self.log_message(
                f"Report available: {label}",
                level="SUCCESS"
            )