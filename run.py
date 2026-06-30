"""Launch the Auto Bibliography Generator and open it in the browser.

For non-technical users: double-click this file (or run `python run.py`). It
starts the local server and opens your browser. Nothing leaves your computer.
"""
from __future__ import annotations

import threading
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORT = 8000


def _open_browser() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}/")


if __name__ == "__main__":
    threading.Timer(1.2, _open_browser).start()
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info")
