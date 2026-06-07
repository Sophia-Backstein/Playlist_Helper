"""Cover art popup dialog for viewing and selecting album art."""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox,
)


class CoverPopup(QDialog):
    """Popup dialog showing a larger preview of the cover art.
    
    Double-clicking on the cover thumbnail in the track entry opens this.
    Contains a "Select Image" button to choose a new cover image file.
    """
    
    def __init__(
        self,
        current_image_path: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._image_path: Optional[str] = current_image_path
        self._initial_image_path: Optional[str] = current_image_path
        self._selected_image_path: Optional[str] = None
        self._cover_changed: bool = False
        
        self.setWindowTitle("Album Cover Art")
        self.setMinimumSize(400, 450)
        self.setModal(True)
        
        self._setup_ui()
        self._load_image()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        # Image preview label
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumSize(300, 300)
        self._image_label.setStyleSheet(
            "QLabel { border: 2px dashed #555; border-radius: 8px; "
            "background-color: #222; }"
        )
        layout.addWidget(self._image_label)
        
        # Info label
        self._info_label = QLabel("No cover image set")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self._info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self._select_btn = QPushButton("Select Image")
        self._select_btn.clicked.connect(self._on_select_image)
        button_layout.addWidget(self._select_btn)
        
        self._clear_btn = QPushButton("Remove Cover")
        self._clear_btn.clicked.connect(self._on_clear_image)
        button_layout.addWidget(self._clear_btn)
        
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self._close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_image(self) -> None:
        """Load and display the current image."""
        if self._image_path and os.path.exists(self._image_path):
            pixmap = QPixmap(self._image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    350, 350,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._image_label.setPixmap(scaled)
                self._info_label.setText(os.path.basename(self._image_path))
                self._info_label.setStyleSheet("color: #aaa;")
                return
        
        # No image
        self._image_label.clear()
        self._image_label.setText("No Cover Art")
        self._image_label.setStyleSheet(
            "QLabel { border: 2px dashed #555; border-radius: 8px; "
            "background-color: #222; color: #666; font-size: 16px; }"
        )
        self._info_label.setText("No cover image set")
        self._info_label.setStyleSheet("color: #888; font-style: italic;")
    
    def _on_select_image(self) -> None:
        """Handle select image button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Cover Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if file_path:
            self._image_path = file_path
            self._selected_image_path = file_path
            self._cover_changed = True
            self._load_image()
    
    def _on_clear_image(self) -> None:
        """Handle remove cover button click."""
        reply = QMessageBox.question(
            self,
            "Remove Cover Art",
            "Remove the album cover image?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._image_path = None
            self._selected_image_path = None
            self._cover_changed = True
            self._load_image()
    
    @property
    def selected_image_path(self) -> Optional[str]:
        """Get the selected image path (None if cleared).
        
        Returns None when user didn't change the cover,
        or explicitly cleared it. The caller should check
        has_changed to distinguish "no change" from "cleared".
        """
        return self._selected_image_path if self._cover_changed else self._initial_image_path
    
    @property
    def has_changed(self) -> bool:
        """Whether the user actually made a change."""
        return self._cover_changed
