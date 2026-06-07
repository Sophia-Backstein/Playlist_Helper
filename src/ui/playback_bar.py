"""Playback bar widget for previewing audio tracks."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtGui import QFont
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QWidget,
)


def _format_ms(ms: int) -> str:
    """Format milliseconds to mm:ss string.
    
    Returns '--:--' for negative or unknown duration values.
    """
    if ms < 0:
        return "--:--"
    total_sec = ms // 1000
    m, s = divmod(total_sec, 60)
    return f"{m}:{s:02d}"


class PlaybackBar(QWidget):
    """Horizontal playback control bar.

    Contains a play/pause toggle, speed cycle button (1×/2×/4×),
    a position slider, and a current-time / total-time label.

    Designed to be embedded in the VolumePanel between the equalizer
    buttons and the info label.
    """

    _SPEEDS = [1.0, 2.0, 4.0]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        self._speed_index = 0
        self._is_playing = False
        self._slider_dragging = False

        self._setup_ui()
        self._connect_signals()
        self._set_idle_state()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            PlaybackBar {
                background-color: #1a1a1a;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Play/Pause button
        self._play_btn = QPushButton("\u25B6")  # ▶
        self._play_btn.setFixedSize(36, 28)
        self._play_btn.setToolTip("Play / Pause")
        self._play_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a84ff;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
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
                color: #555;
            }
        """)
        self._play_btn.clicked.connect(self._on_play_pause)
        layout.addWidget(self._play_btn)

        # Speed button
        self._speed_btn = QPushButton("1\u00D7")  # 1×
        self._speed_btn.setFixedSize(44, 28)
        self._speed_btn.setToolTip("Playback speed (cycle 1× → 2× → 4×)")
        self._speed_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: #ccc;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #555;
                border-color: #0a84ff;
            }
            QPushButton:pressed {
                background-color: #333;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #444;
            }
        """)
        self._speed_btn.clicked.connect(self._on_cycle_speed)
        layout.addWidget(self._speed_btn)

        # Position slider
        self._position_slider = QSlider(Qt.Orientation.Horizontal)
        self._position_slider.setRange(0, 0)
        self._position_slider.setValue(0)
        self._position_slider.setToolTip("Drag to seek, playback starts from here")
        self._position_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #333;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0a84ff;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #3a9eff;
            }
            QSlider::sub-page:horizontal {
                background: #0a84ff;
                border-radius: 3px;
            }
        """)
        self._position_slider.sliderPressed.connect(self._on_slider_pressed)
        self._position_slider.sliderMoved.connect(self._on_slider_moved)
        self._position_slider.sliderReleased.connect(self._on_slider_released)
        layout.addWidget(self._position_slider, 1)

        # Time label
        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setFixedWidth(100)
        self._time_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._time_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._time_label)

    def _connect_signals(self) -> None:
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)

    def _set_idle_state(self) -> None:
        self._play_btn.setText("\u25B6")
        self._play_btn.setEnabled(False)
        self._speed_btn.setEnabled(False)
        self._position_slider.setEnabled(False)
        self._position_slider.setRange(0, 0)
        self._position_slider.setValue(0)
        self._time_label.setText("0:00 / 0:00")
        self._is_playing = False

    # --- Public API ---

    def set_track(self, file_path: str) -> None:
        """Load and prepare a track for playback.

        Resets position to 0, stops any current playback,
        clears any cached state from previous inode, and sets
        the media source to the given file.
        """
        self._player.stop()
        # Clear source to force Qt's FFmpeg backend to fully reset
        # its internal state. Without this, a file whose inode was
        # atomically replaced (os.replace) can cause stale metadata
        # (e.g., doubled duration) to bleed into the new playback.
        self._player.setSource(QUrl())
        self._is_playing = False
        self._play_btn.setText("\u25B6")
        self._position_slider.setRange(0, 0)
        self._position_slider.setValue(0)
        self._time_label.setText("0:00 / 0:00")
        self._player.setSource(QUrl.fromLocalFile(file_path))
        self._speed_index = 0
        self._player.setPlaybackRate(self._SPEEDS[0])
        self._speed_btn.setText("1\u00D7")
        self._play_btn.setEnabled(True)
        self._speed_btn.setEnabled(True)
        self._position_slider.setEnabled(True)

    def stop(self) -> None:
        """Stop playback and reset to idle state."""
        self._player.stop()
        self._set_idle_state()

    # --- UI callbacks ---

    def _on_play_pause(self) -> None:
        if self._is_playing:
            self._player.pause()
        else:
            self._player.play()

    def _on_cycle_speed(self) -> None:
        self._speed_index = (self._speed_index + 1) % len(self._SPEEDS)
        speed = self._SPEEDS[self._speed_index]
        self._player.setPlaybackRate(speed)
        label = f"{speed:.0f}\u00D7" if speed >= 1.0 else f"{speed:.1f}\u00D7"
        self._speed_btn.setText(label)

    def _on_slider_pressed(self) -> None:
        self._slider_dragging = True

    def _on_slider_moved(self, pos: int) -> None:
        dur = self._player.duration()
        self._time_label.setText(
            f"{_format_ms(pos)} / {_format_ms(dur)}"
        )

    def _on_slider_released(self) -> None:
        pos = self._position_slider.value()
        self._player.setPosition(pos)
        self._slider_dragging = False

    # --- Player callbacks ---

    @Slot()
    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self._is_playing = (state == QMediaPlayer.PlaybackState.PlayingState)
        self._play_btn.setText("\u23F8" if self._is_playing else "\u25B6")

    @Slot()
    def _on_position_changed(self, pos: int) -> None:
        if not self._slider_dragging:
            self._position_slider.setValue(pos)
            dur = self._player.duration()
            self._time_label.setText(
                f"{_format_ms(pos)} / {_format_ms(dur)}"
            )

    @Slot()
    def _on_duration_changed(self, dur: int) -> None:
        self._position_slider.setRange(0, max(dur, 0))

    @Slot()
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._player.stop()
            self._is_playing = False
            self._play_btn.setEnabled(False)
            self._speed_btn.setEnabled(False)
            self._position_slider.setEnabled(False)
        elif status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.Buffered,
        ):
            self._play_btn.setEnabled(True)
            self._position_slider.setEnabled(True)
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._player.stop()
            self._player.setPosition(0)
            self._is_playing = False
            self._play_btn.setText("\u25B6")
            self._slider_dragging = False
            self._position_slider.setValue(0)
            dur = self._player.duration()
            self._time_label.setText(
                f"0:00 / {_format_ms(dur)}"
            )
