from jinja2  import Template
import subprocess
import os

class OutputManager:
    def __init__(self, output_widget, html_file_path="output.html", parent=None):
        self.output_widget = output_widget
        self.html_file_path = html_file_path
        self.file_created = False
        self.output_logs = []
        self.file_format_links = []
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
        <div class="log">
            {% if logs %}
                <ul>
                    {% for log in logs %}
                        <li>{{ log | safe }}</li>
                    {% endfor %}
                </ul>
            {% else %}
                <p>No logs available yet.</p>
            {% endif %}
        </div>
        
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
            print(f"Failed to open file in Notepad: {e}")

    def append_content(self, content):
        current_content = self.output_widget.toHtml()
        print(f" Current HTML Content: {current_content}")
        print(f"current content {type(current_content)}")
        self.output_widget.setHtml(current_content + content)

    def clear_output(self):
        self.output_widget.clear()

    def save_to_html_file(self, html_content):
        # Check if file exists before appending for the first time
        if not self.file_created:
            # Create and open the file in write mode to ensure it exists
            with open(self.html_file_path, "w") as file:
                file.write("")  # Write empty content initially
            print(f"HTML file created at: {os.path.abspath(self.html_file_path)}")
            print(f"HTML CONTENT: {html_content}")
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
        }
        full_content = self.combined_template.render(data)
        
        # Update file and display without overwriting other sections
        self.update_full_display(full_content)
        
        
    def update_full_display(self, full_content):
        
        # Write to the HTML file and update the display
        with open(self.html_file_path, "w", encoding="utf-8") as file:
            file.write(full_content)
        
        # Read from the HTML file and update the QTextEdit widget
        with open(self.html_file_path, "r", encoding="utf-8") as file:
            self.output_widget.setHtml(file.read())
 
        
    def load_html_to_output(self):
        # Read HTML content and display in the output widget
        with open(self.html_file_path, "r", encoding="utf-8") as file:
            content = file.read()
        self.output_widget.setHtml(content)
        
    def log_message(self, message, **_):
    # Append message to logs and update display
        self.output_logs.append(message)
        self.update_display(
            self.parent_app.selected_drives_list,
            self.parent_app.selected_directories_list,
            self.parent_app.formatted_drive_digital_ids_list,
            self.parent_app.formatted_directory_digital_ids_list,
            self.parent_app.output_directory,
            self.parent_app.selected_drives_digID_dictionary,
            self.parent_app.selected_directories_digID_dictionary
        ) 