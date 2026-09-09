from PyQt5.QtCore import QThread, pyqtSignal
import subprocess
import os
import time
import chardet



class DirectoryListingWorker(QThread):
    progress_signal = pyqtSignal(str)   # Signal for progress messages
    completed_signal = pyqtSignal(dict) # Signal to send the results back
    output_signal = pyqtSignal(str)     # Signal to send output to the main thread
    html_signal = pyqtSignal(str)       # Signal to append HTML to the main thread
    
    def __init__(self, input_dict, output_directory, task_type="directory"):
        super().__init__()
        self.input_dict = input_dict
        self.output_directory = output_directory
        self.task_type = task_type
        
        print(f"def__init__--directory_listing:\nself.input_dict: {self.input_dict}\nself.output_directory: {self.output_directory}\nself.task_type:{self.task_type}")

    def run(self):
        results = {}
        task_label = "Drive" if self.task_type == "drive" else "Directory"
        listing_output_dir = os.path.join(self.output_directory, "directory_listing_output")
        os.makedirs(listing_output_dir, exist_ok=True)

        for key, value in self.input_dict.items():
            print(f"DirectoryListingWorker run--key: {key}, value: {value}, task_type: {self.task_type}")
            # Verify target path
            if self.task_type == "drive" and not os.path.ismount(value):
                self.progress_signal.emit(f"Not a valid drive: {value}")
                continue
            elif self.task_type == "directory" and not os.path.isdir(value):
                self.progress_signal.emit(f"Not a valid directory: {value}")
                continue

            output_path = os.path.join(listing_output_dir, f"{key}_dir.txt")
            cmd_output = f'dir "{value}" /a /s /t:w'
            print(f"DirectoryListingWorker run--cmd_output: {cmd_output}")
            bat_command = f'start /B cmd /c {cmd_output} > "{output_path}"'
            print(f"Bat command: {bat_command}")

            try:
                self.progress_signal.emit(f"🔍 {task_label} Listing: {value}")
                subprocess.Popen(bat_command, shell=True)

                # Wait for output file to appear
                while not os.path.exists(output_path):
                    time.sleep(0.5)

                self.progress_signal.emit(f"Completed listing for: {value}")
                results[key] = output_path

                if self.task_type == "drive":
                    # Capture stdout for GUI inline display
                    raw_cmd = subprocess.run(cmd_output, shell=True, check=True, stdout=subprocess.PIPE)
                    encoding = chardet.detect(raw_cmd.stdout)['encoding']
                    output_text = raw_cmd.stdout.decode(encoding)

                    self.output_signal.emit(f"Output for {key}:\n{output_text}")
                    self.html_signal.emit(f"<h3>Drive {key} Output:</h3><pre>{output_text}</pre>")

            except subprocess.CalledProcessError as e:
                self.progress_signal.emit(f" Error listing {value}: {e}")

        self.completed_signal.emit(results)