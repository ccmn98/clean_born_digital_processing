import json
import subprocess
from datetime import date
from pathlib import Path
import shutil



ROOT_DIR = Path(__file__).resolve().parent
VERSION_FILE = ROOT_DIR / "version.json"


def get_git_build_number():
    return int(
        subprocess.check_output(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=ROOT_DIR,
            text=True,
        ).strip()
    )


def get_git_commit():
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT_DIR,
        text=True,
    ).strip()


def main():
    
    if shutil.which("git") is None:
        raise SystemExit(
            "ERROR: Git was not found. "
            "Please install Git for Windows and ensure "
            "it is included in the system PATH."
        )
        
    with VERSION_FILE.open("r", encoding="utf-8") as f:
        version_info = json.load(f)

    version_info["build"] = get_git_build_number()
    version_info["build_date"] = date.today().isoformat()
    version_info["commit"] = get_git_commit()

    with VERSION_FILE.open("w", encoding="utf-8") as f:
        json.dump(version_info, f, indent=4)

    print("Updated version.json:")
    print(f"  Version: {version_info['version']}")
    print(f"  Build: {version_info['build']}")
    print(f"  Date: {version_info['build_date']}")
    print(f"  Commit: {version_info['commit']}")


if __name__ == "__main__":
    main()