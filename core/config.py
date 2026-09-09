import os
from pathlib import Path
import tempfile

# --- GENERAL SETTINGS ---
APP_NAME = "Born-Digital Processing"
VERSION = "1.0.0"

# --- DIRECTORY SETTINGS ---
USER_HOME = Path.home()  # Get user's home directory
bagger_profile_target_path = os.path.join(USER_HOME, 'bagger')


# --- FILE FORMATS ---
SUPPORTED_FILE_FORMATS = ["json", "txt", "csv", "xml", "pdf"]

# --- BATCH COMMANDS ---
DIR_COMMAND_TEMPLATE = 'dir "{path}" /a /s > "{output}"'
DIR_COMMAND_VIEWABLE_TEMPLATE = 'dir "{path}" /a /s /t:w'

# --- UI SETTINGS ---
WINDOW_GEOMETRY = (375, 150, 1200, 600)  # (x, y, width, height)
FONT_FAMILY = "Times"
FONT_SIZE = 8

# --- HTML SETTINGS FOR OUTPUT ---
HTML_TEMPLATE = """
<style>
    body { font-family: Consolas, monospace; }
    .log { color: green; }
</style>

<h3>Selected Drives and Directories:</h3>
<ul>
    {% for item in drives %} <li>{{ item }}</li> {% endfor %}
    {% for item in directories %} <li>{{ item }}</li> {% endfor %}
</ul>

<h3>Processing Logs:</h3>
<div class="log">
    {% for log in logs %} <li>{{ log | safe }}</li> {% endfor %}
</div>
"""

# --- FLASK SERVER SETTINGS (IF USED) ---
FLASK_HOST = "localhost"
FLASK_PORT = 5000
FLASK_TIMEOUT = 2  # seconds before assuming server isn't running


# ---------------------------------------------------------
# Application-specific directories stored on the workstation
# ---------------------------------------------------------

APP_DIR = Path.home() / ".BornDigitalProcessing"

LOG_DIR = APP_DIR / "logs"

TEMP_DIR = APP_DIR / "temp"


def ensure_app_directories():
    """
    Create application directories that are stored on the
    user's workstation.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)