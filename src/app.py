"""Application entry point and setup."""

from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from src.ui.main_window import MainWindow


def _check_ffmpeg() -> bool:
    """Check that FFmpeg and FFprobe are available on the system.
    
    Shows an error dialog and returns False if either is missing.
    """
    missing = []
    for cmd in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run(
                [cmd, "-version"],
                capture_output=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            missing.append(cmd)
    
    if missing:
        # Must show error before QApplication event loop starts,
        # so we print to stderr and let the caller handle it
        print(
            f"ERROR: Required tools not found: {', '.join(missing)}\n"
            f"Install FFmpeg: sudo dnf install ffmpeg",
            file=sys.stderr,
        )
        return False
    return True


def create_app() -> QApplication:
    """Create and configure the QApplication instance.
    
    Sets up application-wide styles, attributes, and the dark theme.
    
    Returns:
        Configured QApplication instance.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Playlist Helper")
    app.setOrganizationName("PlaylistHelper")
    app.setApplicationVersion("1.0.0")
    
    return app


def run() -> None:
    """Create and run the application."""
    if not _check_ffmpeg():
        # Start QApp briefly to show error dialog, then exit
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Missing Dependency",
            "FFmpeg and FFprobe are required but were not found.\n\n"
            "Install with:\n"
            "  Fedora: sudo dnf install ffmpeg\n"
            "  Debian/Ubuntu: sudo apt install ffmpeg\n"
            "  Windows: Download from https://ffmpeg.org/download.html\n\n"
            "Make sure ffmpeg and ffprobe are in your PATH.",
        )
        sys.exit(1)
    
    app = create_app()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
