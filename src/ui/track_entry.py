"""Individual track entry widget with all interactive components."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QFileDialog, QMessageBox,
    QSizePolicy,
)

from src.models.track import Track
from src.ui.range_slider import RangeSlider
from src.ui.cover_popup import CoverPopup
from src.utils.time_format import format_seconds


class TrackEntry(QFrame):
    """Widget representing a single audio track entry with all controls.
    
    Contains: range slider, filename input, title input, cover art,
    format dropdown, volume display, save/reset buttons.
    """
    
    def __init__(
        self,
        track: Track,
        on_save: Optional[Callable[[Track], None]] = None,
        on_reset: Optional[Callable[[Track], None]] = None,
        on_field_edit: Optional[Callable[[Track, Dict[str, Any]], None]] = None,
        on_select: Optional[Callable[[Track], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._track = track
        self._on_save = on_save
        self._on_reset = on_reset
        self._on_field_edit = on_field_edit
        self._on_select = on_select
        self._selected = False
        self._cover_pixmap: Optional[QPixmap] = None
        
        self._setup_ui()
        self._populate_from_track()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle click to select this track for playback."""
        if self._on_select:
            self._on_select(self._track)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        """Highlight this entry as the currently selected track."""
        self._selected = selected
        border = "#0a84ff" if selected else "#333"
        self.setStyleSheet(f"""
            TrackEntry {{
                background-color: #1e1e1e;
                border: 2px solid {border};
                border-radius: 6px;
                margin: 2px 0px;
            }}
            TrackEntry:hover {{
                border-color: #555;
            }}
        """)

    @property
    def is_selected(self) -> bool:
        """Whether this entry is the currently selected track."""
        return self._selected

    def _setup_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            TrackEntry {
                background-color: #1e1e1e;
                border: 2px solid #333;
                border-radius: 6px;
                margin: 2px 0px;
            }
            TrackEntry:hover {
                border-color: #555;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(6)
        
        # Top row: filename + title
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        
        # File icon + name label
        self._file_label = QLabel("🎵")
        self._file_label.setFixedSize(24, 24)
        top_row.addWidget(self._file_label)
        
        # Filename input
        file_layout = QVBoxLayout()
        file_layout.setSpacing(1)
        file_label = QLabel("Filename:")
        file_label.setStyleSheet("color: #888; font-size: 10px;")
        file_layout.addWidget(file_label)
        
        self._filename_input = QLineEdit()
        self._filename_input.setPlaceholderText("Output filename...")
        self._filename_input.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 3px 6px;
            }
            QLineEdit:focus {
                border-color: #0a84ff;
            }
        """)
        self._filename_input.textChanged.connect(self._on_field_changed)
        self._filename_input.editingFinished.connect(self._on_filename_edited)
        file_layout.addWidget(self._filename_input)
        top_row.addLayout(file_layout, 2)
        
        # Title input
        title_layout = QVBoxLayout()
        title_layout.setSpacing(1)
        title_label = QLabel("Title:")
        title_label.setStyleSheet("color: #888; font-size: 10px;")
        title_layout.addWidget(title_label)
        
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Music title...")
        self._title_input.setStyleSheet(self._filename_input.styleSheet())
        self._title_input.textChanged.connect(self._on_field_changed)
        self._title_input.editingFinished.connect(self._on_title_edited)
        title_layout.addWidget(self._title_input)
        top_row.addLayout(title_layout, 2)
        
        main_layout.addLayout(top_row)
        
        # Range slider row
        slider_layout = QVBoxLayout()
        slider_layout.setSpacing(1)
        slider_label = QLabel("Trim Range:")
        slider_label.setStyleSheet("color: #888; font-size: 10px;")
        slider_layout.addWidget(slider_label)
        
        self._range_slider = RangeSlider(
            duration_seconds=self._track.duration_seconds,
        )
        self._range_slider.range_changed.connect(self._on_range_changed)
        slider_layout.addWidget(self._range_slider)
        
        main_layout.addLayout(slider_layout)
        
        # Bottom row: cover art, format, volume, actions
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)
        
        # Cover art
        cover_layout = QVBoxLayout()
        cover_layout.setSpacing(1)
        cover_label = QLabel("Cover:")
        cover_label.setStyleSheet("color: #888; font-size: 10px;")
        cover_layout.addWidget(cover_label)
        
        self._cover_label = QLabel()
        self._cover_label.setFixedSize(60, 60)
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setStyleSheet("""
            QLabel {
                border: 1px solid #444;
                border-radius: 4px;
                background-color: #2a2a2a;
            }
        """)
        self._cover_label.mouseDoubleClickEvent = self._on_cover_double_click
        self._cover_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cover_label.setToolTip("Double-click to change cover art")
        cover_layout.addWidget(self._cover_label)
        bottom_row.addLayout(cover_layout)
        
        # Format dropdown
        format_layout = QVBoxLayout()
        format_layout.setSpacing(1)
        fmt_label = QLabel("Format:")
        fmt_label.setStyleSheet("color: #888; font-size: 10px;")
        format_layout.addWidget(fmt_label)
        
        self._format_combo = QComboBox()
        self._format_combo.addItems(["mp3", "wav", "flac"])
        self._format_combo.setStyleSheet("""
            QComboBox {
                background-color: #2a2a2a;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 3px 6px;
                min-width: 80px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #888;
                margin-right: 6px;
            }
            QComboBox:hover {
                border-color: #0a84ff;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                color: #ddd;
                selection-background-color: #0a84ff;
            }
        """)
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        format_layout.addWidget(self._format_combo)
        bottom_row.addLayout(format_layout)
        
        # Volume section
        volume_layout = QVBoxLayout()
        volume_layout.setSpacing(1)
        vol_label = QLabel("Volume:")
        vol_label.setStyleSheet("color: #888; font-size: 10px;")
        volume_layout.addWidget(vol_label)
        
        # Average volume (read-only display)
        avg_vol_layout = QHBoxLayout()
        avg_vol_layout.setSpacing(4)
        avg_vol_label = QLabel("Avg:")
        avg_vol_label.setStyleSheet("color: #aaa; font-size: 10px;")
        avg_vol_layout.addWidget(avg_vol_label)
        
        self._avg_vol_display = QLabel("-- dB")
        self._avg_vol_display.setStyleSheet("color: #ccc; font-size: 11px;")
        avg_vol_layout.addWidget(self._avg_vol_display)
        volume_layout.addLayout(avg_vol_layout)
        
        # Cleaned average (editable)
        clean_layout = QHBoxLayout()
        clean_layout.setSpacing(4)
        clean_label = QLabel("Clean:")
        clean_label.setStyleSheet("color: #aaa; font-size: 10px;")
        clean_layout.addWidget(clean_label)
        
        self._cleaned_avg_input = QLineEdit()
        self._cleaned_avg_input.setPlaceholderText("dB")
        self._cleaned_avg_input.setStyleSheet(self._filename_input.styleSheet())
        self._cleaned_avg_input.setFixedWidth(80)
        self._cleaned_avg_input.textChanged.connect(self._on_field_changed)
        self._cleaned_avg_input.editingFinished.connect(self._on_cleaned_avg_edited)
        clean_layout.addWidget(self._cleaned_avg_input)
        volume_layout.addLayout(clean_layout)
        
        bottom_row.addLayout(volume_layout)
        
        # Spacer
        bottom_row.addStretch()
        
        # Save and Reset buttons
        action_layout = QVBoxLayout()
        action_layout.setSpacing(4)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        
        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a84ff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0a6ed1;
            }
            QPushButton:pressed {
                background-color: #0858a3;
            }
        """)
        self._save_btn.clicked.connect(self._on_save_clicked)
        action_layout.addWidget(self._save_btn)
        
        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: #ddd;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px 18px;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton:pressed {
                background-color: #333;
            }
        """)
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        action_layout.addWidget(self._reset_btn)
        
        bottom_row.addLayout(action_layout)
        
        main_layout.addLayout(bottom_row)
    
    def _populate_from_track(self) -> None:
        """Fill UI fields from track data."""
        self._filename_input.setText(self._track.file_name)
        self._title_input.setText(self._track.title)
        self._format_combo.setCurrentText(self._track.format)
        self._range_slider.set_range(
            self._track.trim_start, self._track.trim_end
        )
        
        # Volume display
        if self._track.average_volume_db != 0.0:
            self._avg_vol_display.setText(f"{self._track.average_volume_db:.1f} dB")
        else:
            self._avg_vol_display.setText("-- dB")
        
        if self._track.cleaned_average_db != 0.0:
            self._cleaned_avg_input.setText(f"{self._track.cleaned_average_db:.1f}")
        
        # Cover art
        self._load_cover()
    
    def _load_cover(self) -> None:
        """Load and display cover art."""
        if self._track.cover_image_path and os.path.exists(self._track.cover_image_path):
            pixmap = QPixmap(self._track.cover_image_path)
            if not pixmap.isNull():
                self._cover_pixmap = pixmap
                scaled = pixmap.scaled(
                    56, 56,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._cover_label.setPixmap(scaled)
                self._cover_label.setText("")
                return
        
        # No cover
        self._cover_pixmap = None
        self._cover_label.clear()
        self._cover_label.setText("🎵")
        self._cover_label.setStyleSheet("""
            QLabel {
                border: 1px solid #444;
                border-radius: 4px;
                background-color: #2a2a2a;
                font-size: 20px;
            }
        """)
    
    def _on_cover_double_click(self, event) -> None:
        """Handle double-click on cover art to open popup."""
        old_path = self._track.cover_image_path
        popup = CoverPopup(
            current_image_path=old_path,
            parent=self,
        )
        if popup.exec() == CoverPopup.Accepted and popup.has_changed:
            new_path = popup.selected_image_path
            self._track.cover_image_path = new_path
            self._track.has_cover = new_path is not None
            self._track.is_dirty = True
            self._load_cover()
            if self._on_field_edit:
                self._on_field_edit(self._track, {"cover_image_path": old_path})
    
    def _on_range_changed(self, start: float, end: float) -> None:
        """Handle range slider change."""
        old_start = self._track.trim_start
        old_end = self._track.trim_end
        self._track.trim_start = start
        self._track.trim_end = end
        self._track.is_dirty = True
        if self._on_field_edit and (old_start != start or old_end != end):
            self._on_field_edit(
                self._track,
                {"trim_start": old_start, "trim_end": old_end},
            )
    
    def _on_field_changed(self) -> None:
        """Handle any field change (dirty tracking only)."""
        self._track.is_dirty = True
    
    def _on_filename_edited(self) -> None:
        """Handle filename edit finished (enter/focus loss)."""
        old_name = self._track.file_name
        new_name = self._filename_input.text().strip()
        if new_name and new_name != old_name:
            self._track.file_name = new_name
            if self._on_field_edit:
                self._on_field_edit(self._track, {"file_name": old_name})
    
    def _on_title_edited(self) -> None:
        """Handle title edit finished (enter/focus loss)."""
        old_title = self._track.title
        new_title = self._title_input.text().strip()
        if new_title != old_title:
            self._track.title = new_title
            if self._on_field_edit:
                self._on_field_edit(self._track, {"title": old_title})
    
    def _on_cleaned_avg_edited(self) -> None:
        """Handle cleaned average edit finished (enter/focus loss)."""
        old_val = self._track.cleaned_average_db
        text = self._cleaned_avg_input.text().strip().replace("dB", "").strip()
        try:
            new_val = float(text)
        except ValueError:
            return
        if new_val != old_val:
            self._track.cleaned_average_db = new_val
            if self._on_field_edit:
                self._on_field_edit(self._track, {"cleaned_average_db": old_val})
    
    def _on_format_changed(self) -> None:
        """Handle format dropdown change."""
        old_fmt = self._track.format
        new_fmt = self._format_combo.currentText()
        if new_fmt != old_fmt:
            self._track.format = new_fmt
            self._track.is_dirty = True
            if self._on_field_edit:
                self._on_field_edit(self._track, {"format": old_fmt})
    
    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        # Update track from UI fields
        self._sync_from_ui()
        if self._on_save:
            self._on_save(self._track)
    
    def _on_reset_clicked(self) -> None:
        """Handle reset button click."""
        reply = QMessageBox.question(
            self,
            "Reset Track",
            f'Reset "{self._track.file_name}" to original values?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Call the callback BEFORE reset so it can capture current state
            # for undo/redo. The callback's execute_fn handles the actual reset.
            if self._on_reset:
                self._on_reset(self._track)
            else:
                self._track.reset_to_original()
                self._populate_from_track()
    
    def _sync_from_ui(self) -> None:
        """Sync UI field values back to the track model."""
        self._track.file_name = self._filename_input.text()
        self._track.title = self._title_input.text()
        self._track.format = self._format_combo.currentText()
        self._track.trim_start = self._range_slider.start_seconds
        self._track.trim_end = self._range_slider.end_seconds
        
        try:
            clean_text = self._cleaned_avg_input.text().strip()
            if clean_text and clean_text != "dB":
                cleaned_val = float(clean_text.replace("dB", "").strip())
                self._track.cleaned_average_db = cleaned_val
        except ValueError:
            pass
    
    @property
    def track(self) -> Track:
        """Get the track model associated with this entry."""
        return self._track
    
    def refresh_ui(self) -> None:
        """Refresh all UI elements from the track model."""
        self._populate_from_track()
