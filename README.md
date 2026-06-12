# Playlist Helper

A cross-platform desktop application for managing, editing, and processing audio files. Built with Python and PySide6 (Qt6).

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

## Features

- **Load audio and video files** from folders — audio: mp3, m4a, flac, opus, wav; video: mp4, avi, flv, mkv, webm, mov
- **Trim audio** with a dual-point range slider and visual preview
- **Edit metadata** — filenames, titles, album art
- **Extract audio from video** — convert video files to mp3, wav, or flac
- **Volume analysis & equalization**:
  - "Equalize to Average" — normalize all tracks to the mean volume
  - "Equalize to Loudest" — normalize all tracks to match the loudest track
  - Uses cleaned RMS averaging (middle 80%, discarding top/bottom 10%)
- **Audio preview playback** — play/pause, speed control (1×/2×/4×), seek slider
- **Safe save** — automatic backup before overwriting files
- **Undo/redo** — full command history for all edits
- **Batch operations** — process multiple files at once

## Screenshots

<!-- Add screenshots here -->

## Requirements

- Python 3.10+
- PySide6 6.6+
- FFmpeg (for audio processing, volume analysis)
- Linux: `pulseaudio` or `pipewire` (for audio playback)

## Installation

### From source

```bash
git clone git@github.com:Sophia-Backstein/Playlist_Helper.git
cd Playlist_Helper
pip install -r requirements.txt
python main.py
```

### Linux (system-wide install)

```bash
chmod +x install_linux.sh
sudo ./install_linux.sh
playlist-helper
```

### Build packages

```bash
# RPM (Fedora/RHEL)
make build-rpm

# Debian (Ubuntu/Debian)
make build-deb

# Windows executable (requires PyInstaller)
make build-exe
```

## Usage

```bash
# Launch the application
python main.py

# Run with tests
python main.py --run-tests

# Run tests with file limit per format
python main.py --run-tests --limit-per-format 1
```

### Keyboard shortcuts

- `Ctrl+O` — Open folder
- `Ctrl+Z` — Undo
- `Ctrl+Shift+Z` — Redo
- `Ctrl+S` — Save current track
- `Ctrl+A` — Select all tracks
- Space — Play/Pause (when track selected)

## Project Structure

```
Playlist_Helper/
├── main.py                  # Application entry point
├── setup.py                 # Python package setup
├── requirements.txt         # Python dependencies
├── Makefile                 # Build automation
├── src/
│   ├── app.py               # Application lifecycle
│   ├── models/
│   │   └── track.py         # Track data model
│   ├── audio/
│   │   ├── scanner.py       # Folder scanning
│   │   ├── analyzer.py      # Volume analysis (FFmpeg)
│   │   ├── equalizer.py     # Volume equalization
│   │   ├── metadata.py      # Tag/cover editing
│   │   └── processor.py     # Format conversion
│   ├── ui/
│   │   ├── main_window.py   # Main window orchestrator
│   │   ├── topbar.py        # Top toolbar
│   │   ├── track_list.py    # Track list container
│   │   ├── track_entry.py   # Individual track widget
│   │   ├── volume_panel.py  # Volume controls + playback
│   │   ├── playback_bar.py  # Audio playback controls
│   │   ├── range_slider.py  # Dual-point range slider
│   │   └── cover_popup.py   # Cover art popup
│   ├── history/
│   │   └── command.py       # Command history (undo/redo)
│   └── utils/
│       └── file_ops.py      # File operations helpers
├── collect_test_samples.sh  # Batch-collect media into test zip
├── tests/
│   ├── test_all.py          # Full test suite (11 formats × 9 functions)
│   ├── original/            # Place your test media files here
│   └── cover_test.png       # Test image for cover art tests
├── install_linux.sh         # Linux installer
└── LICENSE.txt              # MIT License
```

## Development

### Setup dev environment

```bash
python -m venv .venv
source .venv/bin/activate
make dev-deps
```

### Run tests

```bash
python main.py --run-tests

# Test with specific file limit per format
python main.py --run-tests --limit-per-format 5
```

### Test audio/video files

The test suite processes media files from `tests/original/`. **No media files are
bundled with the repository** due to copyright concerns. You must provide your own.

**To prepare test files:**

1. Place media files (audio or video, ~5 minutes recommended) in these formats in `tests/original/`:
   - **Audio**: `.mp3`, `.wav`, `.flac`, `.m4a`, `.opus`
   - **Video**: `.mp4`, `.avi`, `.flv`, `.mkv`, `.webm`, `.mov`
2. Run `collect_test_samples.sh` from the repository root to batch-collect
   media from the project tree into a zip archive (skips dot-folders).
3. Run the tests — they will detect the files automatically.

The test suite will warn you if no files are found and tell you where to place them.

### Test coverage

The test suite runs each file through all 9 functions. Formats without embedded
metadata support (avi, flv, mkv, mov, mp4, opus, wav, webm) skip title/cover
tests gracefully.

| Function         | Passing formats | Notes |
|-----------------|----------------|-------|
| Loading         | All 11         | Detects audio/video containers correctly |
| Cutting         | All 11         | Trims via ffmpeg with `-vn` for video |
| Conversion      | All 11         | Converts to mp3/wav/flac |
| Filename change | All 11         | Rename on disk |
| Title edit      | flac, m4a, mp3 | 8 container formats skipped (no embedded tags) |
| Cover art       | flac, m4a, mp3 | 8 container formats skipped (no embedded cover) |
| Volume change   | All 11         | +3dB gain; very quiet files skipped (volumedetect precision) |
| Equalize avg    | All 11         | Normalizes to target dB |
| Equalize loudest| All 11         | Normalizes based on loudest track |

## Architecture

- **UI Layer**: PySide6 (Qt6) widgets — main window, track list, playback bar
- **Audio Layer**: FFmpeg subprocess for analysis/processing; QMediaPlayer for playback
- **Data Layer**: Track model with command history for undo/redo
- **Safety**: All file writes use atomic backup + restore on failure

## License

MIT License — see [LICENSE.txt](LICENSE.txt)

Copyright (c) 2026 Sophia Backstein
