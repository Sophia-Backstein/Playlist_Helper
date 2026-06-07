"""Topbar widget with File menu, Undo and Redo buttons."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QFileDialog, QMenu, QMenuBar,
    QSizePolicy,
)


class TopBar(QWidget):
    """Application topbar containing File menu and undo/redo controls."""
    
    def __init__(
        self,
        on_open_folder: Optional[Callable[[], None]] = None,
        on_undo: Optional[Callable[[], None]] = None,
        on_redo: Optional[Callable[[], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._on_open_folder = on_open_folder
        self._on_undo = on_undo
        self._on_redo = on_redo
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(4)
        
        # Style: darker background to stand out
        self.setStyleSheet("""
            TopBar {
                background-color: #2a2a2a;
                border-bottom: 1px solid #444;
            }
        """)
        
        # File menu
        self._file_menu_btn = QPushButton("File")
        self._file_menu_btn.setFlat(True)
        self._file_menu_btn.setStyleSheet("""
            QPushButton {
                color: #ddd;
                padding: 4px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton::menu-indicator { 
                image: none; 
            }
        """)
        
        file_menu = QMenu(self)
        open_folder_action = QAction("Open Folder...", self)
        open_folder_action.triggered.connect(self._on_open_folder_clicked)
        file_menu.addAction(open_folder_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self._on_exit)
        file_menu.addAction(exit_action)
        
        self._file_menu_btn.setMenu(file_menu)
        layout.addWidget(self._file_menu_btn)
        
        # Separator
        separator = QWidget()
        separator.setFixedWidth(1)
        separator.setStyleSheet("background-color: #555;")
        separator.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(separator)
        
        # Undo button
        self._undo_btn = QPushButton("↩ Undo")
        self._undo_btn.setFlat(True)
        self._undo_btn.setEnabled(False)
        self._undo_btn.setStyleSheet("""
            QPushButton {
                color: #ddd;
                padding: 4px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:disabled {
                color: #555;
            }
        """)
        self._undo_btn.clicked.connect(self._on_undo_clicked)
        layout.addWidget(self._undo_btn)
        
        # Redo button
        self._redo_btn = QPushButton("↪ Redo")
        self._redo_btn.setFlat(True)
        self._redo_btn.setEnabled(False)
        self._redo_btn.setStyleSheet("""
            QPushButton {
                color: #ddd;
                padding: 4px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:disabled {
                color: #555;
            }
        """)
        self._redo_btn.clicked.connect(self._on_redo_clicked)
        layout.addWidget(self._redo_btn)
        
        # Spacer to push everything left
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(spacer)
    
    def _on_open_folder_clicked(self) -> None:
        """Handle File > Open Folder menu action."""
        if self._on_open_folder:
            self._on_open_folder()
    
    def _on_exit(self) -> None:
        """Handle Exit menu action."""
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()
    
    def _on_undo_clicked(self) -> None:
        if self._on_undo:
            self._on_undo()
    
    def _on_redo_clicked(self) -> None:
        if self._on_redo:
            self._on_redo()
    
    def set_undo_enabled(self, enabled: bool) -> None:
        """Enable or disable the undo button."""
        self._undo_btn.setEnabled(enabled)
    
    def set_redo_enabled(self, enabled: bool) -> None:
        """Enable or disable the redo button."""
        self._redo_btn.setEnabled(enabled)
