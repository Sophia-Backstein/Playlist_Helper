"""Main application window orchestrating all UI components."""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QFileDialog, QMessageBox, QApplication,
)

from src.models.track import Track
from src.history.command import CommandHistory, CallbackCommand
from src.ui.topbar import TopBar
from src.ui.track_list import TrackList
from src.ui.volume_panel import VolumePanel
from src.audio.scanner import scan_folder
from src.audio.analyzer import analyze_volume_ffmpeg, compute_cleaned_average
from src.audio.metadata import (
    get_duration_ffprobe, verify_file_duration,
    extract_cover_art, read_title_metadata,
    set_cover_art, set_title_metadata,
)
from src.audio.processor import process_and_convert
from src.audio.equalizer import equalize_to_average, equalize_to_loudest
from src.utils.file_ops import save_with_backup, create_temp_file


class WorkerSignals(QObject):
    """Signals for background thread communication with UI."""
    
    progress = Signal(str)
    error = Signal(str)
    finished = Signal()
    track_saved = Signal(str)  # file_path of saved track
    track_path_changed = Signal(str, str)  # old_path, new_path
    equalize_done = Signal()
    loudest_target_ready = Signal(float)  # computed loudest target in dB


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self._command_history = CommandHistory()
        self._tracks: List[Track] = []
        self._current_folder: Optional[str] = None
        self._worker_signals = WorkerSignals()
        self._last_equalize_target: Optional[float] = None
        
        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._update_undo_redo_buttons()
    
    def _setup_window(self) -> None:
        """Configure the main window."""
        self.setWindowTitle("Playlist Helper")
        self.setMinimumSize(900, 600)
        self.resize(1100, 750)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #141414;
            }
        """)
    
    def _setup_ui(self) -> None:
        """Create and arrange all UI components."""
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # TopBar
        self._topbar = TopBar(
            on_open_folder=self._on_open_folder,
            on_undo=self._on_undo,
            on_redo=self._on_redo,
        )
        main_layout.addWidget(self._topbar)
        
        # Splitter for 80/20 split
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setHandleWidth(1)
        self._splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #333;
            }
        """)
        
        # Track list (80%)
        self._track_list = TrackList(
            on_save=self._on_save_track,
            on_reset=self._on_reset_track,
            on_field_edit=self._on_field_edit_track,
            on_track_selected=self._on_track_selected_for_playback,
        )
        self._splitter.addWidget(self._track_list)
        
        # Volume panel (20%)
        self._volume_panel = VolumePanel(
            on_equalize_to_average=self._on_equalize_average,
            on_equalize_to_loudest=self._on_equalize_loudest,
        )
        self._splitter.addWidget(self._volume_panel)
        
        # Set 80/20 ratio
        self._splitter.setSizes([480, 120])
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)
        
        main_layout.addWidget(self._splitter, 1)
        
        # Status bar
        self._status_bar = self.statusBar()
        self._status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #1a1a1a;
                color: #888;
                border-top: 1px solid #333;
                font-size: 11px;
            }
        """)
        self._status_bar.showMessage("Ready — Open a folder to get started")
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._command_history.on_state_change(self._update_undo_redo_buttons)
        
        # Worker signals
        self._worker_signals.progress.connect(self._on_worker_progress)
        self._worker_signals.error.connect(self._on_worker_error)
        self._worker_signals.finished.connect(self._on_worker_finished)
        self._worker_signals.track_saved.connect(self._on_track_saved)
        self._worker_signals.track_path_changed.connect(self._on_track_path_changed)
        self._worker_signals.loudest_target_ready.connect(self._on_loudest_target_ready)
        self._worker_signals.equalize_done.connect(self._on_equalize_done)
    
    def _update_undo_redo_buttons(self) -> None:
        """Update undo/redo button enabled states."""
        self._topbar.set_undo_enabled(self._command_history.can_undo)
        self._topbar.set_redo_enabled(self._command_history.can_redo)
    
    def _on_open_folder(self) -> None:
        """Handle File > Open Folder action."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Music Folder", self._current_folder or "",
        )
        if not folder:
            return
        
        self._current_folder = folder
        self._status_bar.showMessage(f"Scanning: {folder}")
        QApplication.processEvents()
        
        # Scan for audio files
        audio_files = scan_folder(folder)
        
        if not audio_files:
            QMessageBox.information(
                self,
                "No Audio Files",
                f"No supported audio files found in:\n{folder}\n\n"
                f"Supported formats: mp3, m4a, opus, wav, flac",
            )
            self._status_bar.showMessage("No audio files found")
            return
        
        # Stop playback and clear existing tracks
        self._volume_panel._playback_bar.stop()
        self._command_history.clear()
        self._tracks.clear()
        
        # Create track objects
        tracks: List[Track] = []
        self._status_bar.showMessage(
            f"Loading {len(audio_files)} audio files..."
        )
        QApplication.processEvents()
        
        for i, file_path in enumerate(audio_files):
            # Update status periodically
            if i % 5 == 0:
                self._status_bar.showMessage(
                    f"Loading {i + 1}/{len(audio_files)}: "
                    f"{os.path.basename(file_path)}"
                )
                QApplication.processEvents()
            
            duration = get_duration_ffprobe(file_path)
            title = read_title_metadata(file_path)
            
            # Analyze volume
            volume = analyze_volume_ffmpeg(file_path)
            cleaned_avg = compute_cleaned_average(file_path)
            
            # Extract cover art
            cover_path = extract_cover_art(file_path)
            
            # Default format from source extension
            src_ext = os.path.splitext(file_path)[1].lower()
            ext_to_format = {".mp3": "mp3", ".wav": "wav", ".flac": "flac"}
            default_fmt = ext_to_format.get(src_ext, "mp3")

            track = Track(
                file_path=file_path,
                file_name=os.path.basename(file_path),
                title=title,
                duration_seconds=duration,
                format=default_fmt,
                trim_start=0.0,
                trim_end=duration,
                average_volume_db=volume.get("mean_volume", 0.0),
                cleaned_average_db=cleaned_avg,
                max_volume_db=volume.get("max_volume", 0.0),
                cover_image_path=cover_path,
                has_cover=cover_path is not None,
            )
            tracks.append(track)
        
        self._tracks = tracks
        self._track_list.load_tracks(tracks)
        self._volume_panel.set_enabled(len(tracks) > 0)
        self._update_equalize_button_labels()
        
        self._status_bar.showMessage(
            f"Loaded {len(tracks)} audio files from {os.path.basename(folder)}"
        )
    
    def _on_save_track(self, track: Track) -> None:
        """Handle save for a single track.

        Runs the actual processing in a background thread.
        Stops playback and verifies output duration to catch corruption.
        """
        self._volume_panel._playback_bar.stop()

        self._volume_panel.set_progress(
            f"Saving: {track.file_name}..."
        )
        self._topbar.setEnabled(False)
        self._track_list.setEnabled(False)
        self._volume_panel.setEnabled(False)
        
        # Run in thread
        def save_work():
            backup_path: Optional[str] = None
            try:
                # Build output filename
                base_name, _ = os.path.splitext(track.file_name)
                if not base_name:
                    base_name = os.path.splitext(os.path.basename(track.file_path))[0]
                
                output_suffix = f".{track.format}"
                temp_path = create_temp_file(suffix=output_suffix)
                
                # Compute volume gain from cleaned average if available
                volume_gain = None
                if track.cleaned_average_db != 0.0 and track.average_volume_db != 0.0:
                    volume_gain = round(track.cleaned_average_db - track.average_volume_db, 2)
                
                # Process audio: trim + convert + volume
                success = process_and_convert(
                    input_path=track.file_path,
                    output_path=temp_path,
                    target_format=track.format,
                    start_time=track.trim_start,
                    end_time=track.trim_end,
                    volume_gain_db=volume_gain,
                )
                
                if not success or not os.path.exists(temp_path):
                    self._worker_signals.error.emit(
                        f"Failed to process: {track.file_name}"
                    )
                    return
                
                # Set cover art if available
                if track.cover_image_path:
                    set_cover_art(temp_path, track.cover_image_path)

                # Set title metadata
                if track.title:
                    set_title_metadata(temp_path, track.title)

                # Determine correct output path (use filename + format extension)
                old_file_path = track.file_path
                old_ext = os.path.splitext(old_file_path)[1]
                new_ext = f".{track.format}"
                if old_ext.lower() != new_ext or track.file_name != os.path.basename(old_file_path):
                    output_dir = os.path.dirname(old_file_path)
                    output_name = os.path.splitext(track.file_name)[0] + new_ext
                    output_path = os.path.join(output_dir, output_name)
                else:
                    output_path = old_file_path

                expected_duration = track.trim_end - track.trim_start

                # Safe save with backup (backup uses original path)
                backup_path = save_with_backup(temp_path, output_path)

                if expected_duration > 0:
                    if not verify_file_duration(
                        output_path, expected_duration,
                    ):
                        err_msg = (
                            f"Save verification failed for {track.file_name}: "
                            f"expected {expected_duration:.1f}s but got wrong "
                            f"duration. Restoring from backup."
                        )
                        if backup_path and os.path.exists(backup_path):
                            import shutil
                            try:
                                shutil.copy2(backup_path, output_path)
                                err_msg += " Backup restored."
                            except OSError:
                                err_msg += " Could not restore backup."
                        self._worker_signals.error.emit(err_msg)
                        return

                # Update track path if format extension changed
                if output_path != old_file_path:
                    track.file_path = output_path
                    self._worker_signals.track_path_changed.emit(
                        old_file_path, output_path
                    )
                
                self._worker_signals.track_saved.emit(track.file_path)
                
            except Exception as e:
                self._worker_signals.error.emit(
                    f"Error saving {track.file_name}: {str(e)}"
                )
            finally:
                self._worker_signals.finished.emit()
        
        thread = threading.Thread(target=save_work, daemon=True)
        thread.start()
    
    def _on_reset_track(self, track: Track) -> None:
        """Handle reset for a single track."""
        # Create undo/redo command
        old_state = {
            "file_name": track.file_name,
            "title": track.title,
            "format": track.format,
            "trim_start": track.trim_start,
            "trim_end": track.trim_end,
            "cleaned_average_db": track.cleaned_average_db,
            "cover_image_path": track.cover_image_path,
        }
        
        def apply_fn():
            track.reset_to_original()
            self._track_list.refresh_entry(track.file_path)
        
        def undo_fn():
            track.file_name = old_state["file_name"]
            track.title = old_state["title"]
            track.format = old_state["format"]
            track.trim_start = old_state["trim_start"]
            track.trim_end = old_state["trim_end"]
            track.cleaned_average_db = old_state["cleaned_average_db"]
            track.cover_image_path = old_state["cover_image_path"]
            self._track_list.refresh_entry(track.file_path)
        
        cmd = CallbackCommand(
            execute_fn=apply_fn,
            undo_fn=undo_fn,
            description=f"Reset {track.file_name}",
        )
        self._command_history.push(cmd)
        
        self._status_bar.showMessage(f"Reset: {track.file_name}")
    
    def _on_field_edit_track(
        self, track: Track, old_state: Dict[str, Any],
    ) -> None:
        """Handle field edit for undo/redo tracking.
        
        Creates an undoable command that captures the state change.
        old_state contains only the fields that changed.
        """
        # Capture current state for the changed fields
        current = {
            "file_name": track.file_name,
            "title": track.title,
            "format": track.format,
            "trim_start": track.trim_start,
            "trim_end": track.trim_end,
            "cleaned_average_db": track.cleaned_average_db,
            "cover_image_path": track.cover_image_path,
        }
        
        field_names = list(old_state.keys())
        desc = f"Edit {track.file_name} ({', '.join(field_names)})"
        
        def apply_fn():
            for key in old_state:
                setattr(track, key, current[key])
            self._track_list.refresh_entry(track.file_path)
        
        def undo_fn():
            for key, val in old_state.items():
                setattr(track, key, val)
            self._track_list.refresh_entry(track.file_path)
        
        cmd = CallbackCommand(
            execute_fn=apply_fn,
            undo_fn=undo_fn,
            description=desc,
        )
        self._command_history.push(cmd)
    
    def _on_undo(self) -> None:
        """Handle undo button."""
        self._command_history.undo()
        self._status_bar.showMessage("Undo")
    
    def _on_redo(self) -> None:
        """Handle redo button."""
        self._command_history.redo()
        self._status_bar.showMessage("Redo")
    
    def _on_equalize_average(self) -> None:
        """Handle Equalize Volume to Average button."""
        if not self._tracks:
            return
        
        # Get the average of all cleaned (middle 80%) volume values
        avg_values = [
            t.cleaned_average_db for t in self._tracks
            if t.cleaned_average_db != 0.0
        ]
        
        if not avg_values:
            QMessageBox.warning(
                self,
                "No Volume Data",
                "No volume data available. Load audio files first.",
            )
            return
        
        target_db = sum(avg_values) / len(avg_values)
        self._last_equalize_target = target_db

        self._volume_panel._playback_bar.stop()
        self._volume_panel.set_progress(
            f"Equalizing {len(self._tracks)} tracks to {target_db:.1f} dB..."
        )
        self._set_ui_enabled(False)
        
        def work():
            try:
                for track in self._tracks:
                    self._worker_signals.progress.emit(
                        f"Equalizing: {track.file_name}"
                    )
                    result_path = equalize_to_average(
                        track.file_path, target_db
                    )
                    if result_path and result_path != track.file_path:
                        # Copy result back over original, then clean up
                        import shutil
                        shutil.copy2(result_path, track.file_path)
                        os.remove(result_path)
                
                self._worker_signals.equalize_done.emit()
            except Exception as e:
                self._worker_signals.error.emit(
                    f"Equalization error: {str(e)}"
                )
            finally:
                self._worker_signals.finished.emit()
        
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
    
    def _on_equalize_loudest(self) -> None:
        """Handle Equalize Volume to Loudest button.
        
        Computes the cleaned average (middle 80%) for each track,
        finds the maximum (loudest to a human ear) across all tracks,
        and equalizes each track so its cleaned average matches the max.
        """
        if not self._tracks:
            return
        
        self._volume_panel._playback_bar.stop()
        self._volume_panel.set_progress(
            f"Analyzing cleaned averages for {len(self._tracks)} tracks..."
        )
        self._set_ui_enabled(False)
        self._last_equalize_target = None  # don't reuse average target
        
        def work():
            try:
                # Compute cleaned average for each track
                cleaned_averages = {}
                for track in self._tracks:
                    self._worker_signals.progress.emit(
                        f"Analyzing: {track.file_name}"
                    )
                    ca = compute_cleaned_average(track.file_path)
                    cleaned_averages[track.file_path] = ca
                
                # Target = max cleaned average across all tracks (loudest)
                valid = [v for v in cleaned_averages.values() if v != 0.0]
                if not valid:
                    self._worker_signals.error.emit(
                        "Could not compute cleaned averages for any track"
                    )
                    return
                
                target_db = max(valid)
                
                for track in self._tracks:
                    self._worker_signals.progress.emit(
                        f"Equalizing to loudest ({target_db:.1f} dB): "
                        f"{track.file_name}"
                    )
                    result_path = equalize_to_loudest(
                        track.file_path, target_db=target_db,
                    )
                    if result_path and result_path != track.file_path:
                        import shutil
                        shutil.copy2(result_path, track.file_path)
                        os.remove(result_path)
                
                self._worker_signals.equalize_done.emit()
            except Exception as e:
                self._worker_signals.error.emit(
                    f"Equalization error: {str(e)}"
                )
            finally:
                self._worker_signals.finished.emit()
        
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
    
    def _set_ui_enabled(self, enabled: bool) -> None:
        """Enable or disable the UI during background work."""
        self._topbar.setEnabled(enabled)
        self._track_list.setEnabled(enabled)
        self._volume_panel.setEnabled(enabled and len(self._tracks) > 0)

    def _update_equalize_button_labels(self) -> None:
        """Update button labels with target volumes from current tracks.

        Computes the average target from in-memory data (instant) and
        launches a background task to compute the loudest target.
        """
        if not self._tracks:
            self._volume_panel.set_button_labels(avg_target=None, loudest_target=None)
            return

        # Average target: average of all cleaned (middle 80%) volumes
        avg_values = [
            t.cleaned_average_db for t in self._tracks
            if t.cleaned_average_db != 0.0
        ]
        if avg_values:
            avg_target = sum(avg_values) / len(avg_values)
            self._volume_panel.set_button_labels(avg_target=avg_target)

        # Loudest target: compute in background (requires audio analysis)
        def compute_loudest():
            try:
                cleaned_averages = [
                    compute_cleaned_average(t.file_path)
                    for t in self._tracks
                ]
                valid = [v for v in cleaned_averages if v != 0.0]
                if valid:
                    max_cleaned = max(valid)
                    self._worker_signals.loudest_target_ready.emit(max_cleaned)
            except Exception:
                pass

        thread = threading.Thread(target=compute_loudest, daemon=True)
        thread.start()
    
    # Worker signal handlers
    def _on_worker_progress(self, message: str) -> None:
        self._status_bar.showMessage(message)
        self._volume_panel.set_progress(message)
    
    def _on_worker_error(self, message: str) -> None:
        QMessageBox.critical(self, "Error", message)
        self._status_bar.showMessage(f"Error: {message}")
    
    def _on_worker_finished(self) -> None:
        self._set_ui_enabled(True)
        self._volume_panel.set_info("")
    
    def _on_track_saved(self, file_path: str) -> None:
        """Handle successful track save."""
        self._status_bar.showMessage(
            f"Saved: {os.path.basename(file_path)}"
        )

    def _on_track_path_changed(self, old_path: str, new_path: str) -> None:
        """Update UI after track file path changed (format conversion)."""
        self._track_list.update_entry_path(old_path, new_path)

    def _on_track_selected_for_playback(self, track: Track) -> None:
        """Load selected track into the playback bar."""
        self._volume_panel._playback_bar.set_track(track.file_path)
        self._status_bar.showMessage(
            f"Ready to play: {track.file_name}"
        )

    def _on_loudest_target_ready(self, target_db: float) -> None:
        """Update loudest button label when loudest target is computed."""
        self._volume_panel.set_button_labels(loudest_target=target_db)

    def _on_equalize_done(self) -> None:
        """Handle equalization completion.
        
        Re-analyze volumes immediately since shutil.copy2 is synchronous
        and file I/O is complete by the time this signal fires.
        """
        self._volume_panel.set_info("Volume equalization complete!")
        self._status_bar.showMessage("Volume equalization complete")
        self._reanalyze_volumes()
    
    def _reanalyze_volumes(self) -> None:
        """Re-analyze volumes after equalization.

        After equalize-to-average: cleaned_average_db is set to the
        target value (matching the overall average after equalization).
        After equalize-to-loudest: both values are re-computed from audio.
        """
        self._status_bar.showMessage("Re-analyzing volumes...")
        for track in self._tracks:
            volume = analyze_volume_ffmpeg(track.file_path)
            track.average_volume_db = volume.get("mean_volume", 0.0)
            track.max_volume_db = volume.get("max_volume", 0.0)

            if self._last_equalize_target is not None:
                track.cleaned_average_db = self._last_equalize_target
            else:
                track.cleaned_average_db = compute_cleaned_average(track.file_path)

            self._track_list.refresh_entry(track.file_path)

        self._last_equalize_target = None
        self._update_equalize_button_labels()
        self._status_bar.showMessage(
            f"Volume analysis updated for {len(self._tracks)} tracks"
        )
