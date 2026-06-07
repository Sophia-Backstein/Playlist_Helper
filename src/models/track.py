"""Track data model for audio entries."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Track:
    """Represents a single audio track in the playlist.
    
    Attributes:
        file_path: Absolute path to the audio file.
        file_name: Original filename (for display, editable by user).
        title: Music title metadata (separate from filename).
        duration_seconds: Total duration of the audio file.
        format: Output format selected by user ("mp3", "wav", or "flac").
        trim_start: Start position for trimming in seconds (default 0.0).
        trim_end: End position for trimming in seconds (default = duration).
        average_volume_db: Overall average volume in dB (read-only).
        cleaned_average_db: Average of middle 80% volume in dB (editable).
        max_volume_db: Peak volume in dB (read-only).
        cover_image_path: Path to cover art image file.
        has_cover: Whether cover art was found in metadata.
        is_dirty: Whether changes have been made since last save.
    """
    file_path: str
    file_name: str = ""
    title: str = ""
    duration_seconds: float = 0.0
    format: str = "mp3"
    trim_start: float = 0.0
    trim_end: float = 0.0
    average_volume_db: float = 0.0
    cleaned_average_db: float = 0.0
    max_volume_db: float = 0.0
    cover_image_path: Optional[str] = None
    has_cover: bool = False
    is_dirty: bool = False
    
    # Original values for reset
    _original_file_name: str = ""
    _original_title: str = ""
    _original_format: str = "mp3"
    _original_trim_start: float = 0.0
    _original_trim_end: float = 0.0
    _original_cleaned_average_db: float = 0.0
    _original_cover_image_path: Optional[str] = None

    def __post_init__(self):
        if not self.file_name:
            self.file_name = os.path.basename(self.file_path)
        if self.trim_end == 0.0 and self.duration_seconds > 0:
            self.trim_end = self.duration_seconds
        # Store originals for reset
        self._original_file_name = self.file_name
        self._original_title = self.title
        self._original_format = self.format
        self._original_trim_start = self.trim_start
        self._original_trim_end = self.trim_end
        self._original_cleaned_average_db = self.cleaned_average_db
        self._original_cover_image_path = self.cover_image_path

    def reset_to_original(self):
        """Reset all editable fields to their original values."""
        self.file_name = self._original_file_name
        self.title = self._original_title
        self.format = self._original_format
        self.trim_start = self._original_trim_start
        self.trim_end = self._original_trim_end
        self.cleaned_average_db = self._original_cleaned_average_db
        self.cover_image_path = self._original_cover_image_path
        self.is_dirty = False

    @property
    def file_ext(self) -> str:
        """Get the file extension of the original file."""
        _, ext = os.path.splitext(self.file_path)
        return ext.lower()

    @property
    def output_extension(self) -> str:
        """Get the file extension for the selected output format."""
        return f".{self.format}"

    @property
    def trimmed_duration(self) -> float:
        """Get the duration after trimming."""
        return max(0.0, self.trim_end - self.trim_start)
