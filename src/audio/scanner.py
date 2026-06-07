"""Scan directories for supported audio files."""

from __future__ import annotations

import os
from typing import List

SUPPORTED_EXTENSIONS = {".mp3", ".m4a", ".opus", ".wav", ".flac"}


def scan_folder(folder_path: str) -> List[str]:
    """Scan a folder for supported audio files.
    
    Args:
        folder_path: Path to the folder to scan.
        
    Returns:
        List of absolute file paths for supported audio files.
    """
    if not os.path.isdir(folder_path):
        return []
    
    audio_files: List[str] = []
    try:
        for entry in os.scandir(folder_path):
            if entry.is_file() and not entry.name.startswith("."):
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    audio_files.append(entry.path)
    except PermissionError:
        pass
    
    return sorted(audio_files)


def is_supported_audio(file_path: str) -> bool:
    """Check if a file is a supported audio format.
    
    Args:
        file_path: Path to check.
        
    Returns:
        True if the file has a supported audio extension.
    """
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_EXTENSIONS
