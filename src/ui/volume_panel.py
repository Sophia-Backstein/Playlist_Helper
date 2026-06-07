"""Global volume actions panel (bottom 20% of window)."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSizePolicy,
)

from src.ui.playback_bar import PlaybackBar


class VolumePanel(QWidget):
    """Panel with global volume equalization buttons.
    
    Sits in the bottom 20% of the main window.
    Contains:
    - "Equalize Volume to Average" button
    - "Equalize Volume to Loudest" button
    """
    
    def __init__(
        self,
        on_equalize_to_average: Optional[Callable[[], None]] = None,
        on_equalize_to_loudest: Optional[Callable[[], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._on_equalize_to_average = on_equalize_to_average
        self._on_equalize_to_loudest = on_equalize_to_loudest
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            VolumePanel {
                background-color: #1a1a1a;
                border-top: 2px solid #333;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)
        
        # Header
        header = QLabel("Global Volume Actions")
        header.setStyleSheet("""
            QLabel {
                color: #aaa;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
        """)
        layout.addWidget(header)
        
        # Buttons row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Equalize to Average
        self._avg_btn = QPushButton("Equalize Volume to Average")
        self._avg_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a84ff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0a6ed1;
            }
            QPushButton:pressed {
                background-color: #0858a3;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
            }
        """)
        self._avg_btn.clicked.connect(self._on_avg_clicked)
        button_layout.addWidget(self._avg_btn)
        
        # Equalize to Loudest
        self._loudest_btn = QPushButton("Equalize Volume to Loudest")
        self._loudest_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6b0a;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e05e08;
            }
            QPushButton:pressed {
                background-color: #c05006;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
            }
        """)
        self._loudest_btn.clicked.connect(self._on_loudest_clicked)
        button_layout.addWidget(self._loudest_btn)
        
        layout.addLayout(button_layout)
        
        # Playback bar (between buttons and volume info)
        self._playback_bar = PlaybackBar()
        layout.addWidget(self._playback_bar)
        
        # Info label
        self._info_label = QLabel("")
        self._info_label.setStyleSheet("color: #666; font-size: 10px;")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._info_label)
    
    def _on_avg_clicked(self) -> None:
        if self._on_equalize_to_average:
            self._on_equalize_to_average()
    
    def _on_loudest_clicked(self) -> None:
        if self._on_equalize_to_loudest:
            self._on_equalize_to_loudest()
    
    def set_button_labels(
        self,
        avg_target: Optional[float] = None,
        loudest_target: Optional[float] = None,
    ) -> None:
        """Update button text to show target volume values.

        Args:
            avg_target: Target average volume in dB (None = keep current text).
            loudest_target: Target loudest volume in dB (None = keep current text).
        """
        if avg_target is not None:
            self._avg_btn.setText(
                f"Equalize Volume to Average ({avg_target:.1f} dB)"
            )
        if loudest_target is not None:
            self._loudest_btn.setText(
                f"Equalize Volume to Loudest ({loudest_target:.1f} dB)"
            )

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the volume buttons."""
        self._avg_btn.setEnabled(enabled)
        self._loudest_btn.setEnabled(enabled)
    
    def set_info(self, text: str) -> None:
        """Set informational text."""
        self._info_label.setText(text)
    
    def set_progress(self, message: str) -> None:
        """Show progress message on the panel."""
        self._info_label.setText(message)
        self._info_label.setStyleSheet("color: #0a84ff; font-size: 10px;")
