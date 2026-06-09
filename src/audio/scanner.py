"""Scan directories for supported audio and video files."""

from __future__ import annotations

import os
from typing import List

SUPPORTED_EXTENSIONS = {".mp3", ".m4a", ".opus", ".wav", ".flac"}

VIDEO_EXTENSIONS = {".mp4", ".avi", ".flv", ".mkv", ".webp", ".webm", ".mov"}

SUPPORTED_MEDIA_EXTENSIONS = SUPPORTED_EXTENSIONS | VIDEO_EXTENSIONS


def scan_folder(folder_path: str) -> List[str]:
    """Scan a folder for supported audio and video files.
    
    Args:
        folder_path: Path to the folder to scan.
        
    Returns:
        List of absolute file paths for supported media files.
    """
    if not os.path.isdir(folder_path):
        return []
    
    media_files: List[str] = []
    try:
        for entry in os.scandir(folder_path):
            if entry.is_file() and not entry.name.startswith("."):
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in SUPPORTED_MEDIA_EXTENSIONS:
                    media_files.append(entry.path)
    except PermissionError:
        pass
    
    return sorted(media_files)


def is_supported_audio(file_path: str) -> bool:
    """Check if a file is a supported audio format.
    
    Args:
        file_path: Path to check.
        
    Returns:
        True if the file has a supported audio extension.
    """
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


def is_supported_media(file_path: str) -> bool:
    """Check if a file is a supported audio or video format.
    
    Args:
        file_path: Path to check.
        
    Returns:
        True if the file has a supported media extension.
    """
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_MEDIA_EXTENSIONS


def is_video_file(file_path: str) -> bool:
    """Check if a file is a supported video format.
    
    Args:
        file_path: Path to check.
        
    Returns:
        True if the file has a supported video extension.
    """
    ext = os.path.splitext(file_path)[1].lower()
    return ext in VIDEO_EXTENSIONS
