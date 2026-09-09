from flask import Flask, request
import os

app = Flask(__name__)


@app.route('/open_file')
def open_file():
    file_path = request.args.get('path')

    if file_path and os.path.exists(file_path):
        try:
            os.startfile(file_path)
            return f"Opened file: {file_path}"

        except Exception as e:
            return f"Failed to open file: {str(e)}"

    return "File not found"


if __name__ == "__main__":
    app.run(port=5000)