"""Scrollable list of track entries."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QSizePolicy,
)

from src.models.track import Track
from src.ui.track_entry import TrackEntry


class TrackList(QScrollArea):
    """Scrollable container holding all TrackEntry widgets.
    
    Manages adding, removing, and accessing track entries.
    """
    
    def __init__(
        self,
        on_save: Optional[Callable[[Track], None]] = None,
        on_reset: Optional[Callable[[Track], None]] = None,
        on_field_edit: Optional[Callable[[Track, Dict[str, Any]], None]] = None,
        on_track_selected: Optional[Callable[[Track], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._on_save = on_save
        self._on_reset = on_reset
        self._on_field_edit = on_field_edit
        self._on_track_selected = on_track_selected
        self._entries: Dict[str, TrackEntry] = {}  # file_path -> entry
        self._tracks: List[Track] = []
        self._selected_path: Optional[str] = None
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #141414;
            }
            QScrollBar:vertical {
                background-color: #1a1a1a;
                width: 10px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #444;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #555;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Inner container
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Placeholder when empty
        self._empty_label = QLabel(
            "No audio files loaded.\nOpen a folder with File > Open Folder"
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 16px;
                padding: 40px;
            }
        """)
        self._layout.addWidget(self._empty_label)
        
        self.setWidget(self._container)
    
    def load_tracks(self, tracks: List[Track]) -> None:
        """Replace all tracks with a new list.
        
        Args:
            tracks: List of Track objects to display.
        """
        self.clear()
        self._tracks = list(tracks)
        
        # Remove empty label
        if self._empty_label in self._layout.children():
            self._layout.removeWidget(self._empty_label)
            self._empty_label.hide()
        
        for track in self._tracks:
            entry = TrackEntry(
                track=track,
                on_save=self._on_save,
                on_reset=self._on_reset,
                on_field_edit=self._on_field_edit,
                on_select=self._on_entry_selected,
            )
            self._entries[track.file_path] = entry
            self._layout.addWidget(entry)
        
        self._selected_path = None
        
        # Add stretch at the end
        self._layout.addStretch()
    
    def _on_entry_selected(self, track: Track) -> None:
        """Handle a track entry being clicked for playback."""
        # Deselect previous
        if self._selected_path and self._selected_path in self._entries:
            self._entries[self._selected_path].set_selected(False)
        # Select new
        self._selected_path = track.file_path
        if self._selected_path in self._entries:
            self._entries[self._selected_path].set_selected(True)
        # Notify main window
        if self._on_track_selected:
            self._on_track_selected(track)
    
    def update_entry_path(self, old_path: str, new_path: str) -> None:
        """Update the entry key after a file path change.

        Args:
            old_path: Previous file path key.
            new_path: New file path key.
        """
        if old_path in self._entries:
            entry = self._entries.pop(old_path)
            self._entries[new_path] = entry

    def clear(self) -> None:
        """Remove all track entries."""
        for entry in self._entries.values():
            self._layout.removeWidget(entry)
            entry.deleteLater()
        self._entries.clear()
        self._tracks.clear()
        
        # Remove existing stretch items
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            if item and item.widget() is None:
                self._layout.removeItem(item)
        
        # Show empty label
        self._empty_label.show()
        if self._empty_label not in self._layout.children():
            self._layout.addWidget(self._empty_label)
    
    def get_track(self, file_path: str) -> Optional[Track]:
        """Get a track by file path.
        
        Args:
            file_path: Path to the audio file.
            
        Returns:
            Track if found, None otherwise.
        """
        entry = self._entries.get(file_path)
        if entry:
            # Sync UI before returning
            entry._sync_from_ui()
            return entry.track
        return None
    
    def get_all_tracks(self) -> List[Track]:
        """Get all tracks with UI fields synced.
        
        Returns:
            List of all Track objects.
        """
        for entry in self._entries.values():
            entry._sync_from_ui()
        return list(self._tracks)
    
    def refresh_entry(self, file_path: str) -> None:
        """Refresh the UI for a specific track entry.
        
        Args:
            file_path: Path to the audio file to refresh.
        """
        entry = self._entries.get(file_path)
        if entry:
            entry.refresh_ui()
    
    @property
    def track_count(self) -> int:
        """Get number of tracks loaded."""
        return len(self._tracks)
