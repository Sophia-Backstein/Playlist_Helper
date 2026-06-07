# Playlist Helper

A cross-platform desktop application for managing, editing, and processing audio files. Built with Python and PySide6 (Qt6).

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

## Features

- **Load audio files** from folders — supports mp3, m4a/flac, opus, wav
- **Trim audio** with a dual-point range slider and visual preview
- **Edit metadata** — filenames, titles, album art
- **Convert formats** — between mp3, wav, flac, m4a, opus
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
├── tests/
│   ├── test_all.py          # Full test suite
│   ├── original/            # Place your test audio files here
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

### Test audio files

The test suite processes audio files from `tests/original/`. **No audio files are
bundled with the repository** due to copyright concerns. You must provide your own.

**To prepare test files:**

1. Create or download short audio files (5-15 seconds is plenty) in these formats:
   - `.mp3`, `.wav`, `.flac`, `.m4a` — required for full test coverage
   - `.opus`, `.ogg`, `.aac`, `.wma`, `.m4b`, `.aiff` — optional additional coverage
2. Place them in `tests/original/`
3. Run the tests — they will detect the files automatically

The test suite will warn you if no files are found and tell you where to place them.

### Test coverage

The test suite covers all supported formats and operations:

| Function         | Formats | Status |
|-----------------|---------|--------|
| Loading         | All     | ✅     |
| Cutting         | All     | ✅     |
| Conversion      | All     | ✅     |
| Filename change | All     | ✅     |
| Title edit      | mp3, flac, m4a | ✅ *(wav/opus skipped — no metadata)* |
| Cover art       | mp3, flac, m4a | ✅ *(wav/opus skipped — no cover support)* |
| Volume change   | All     | ✅     |
| Equalize avg    | All     | ✅     |
| Equalize loudest| All     | ✅     |

## Architecture

- **UI Layer**: PySide6 (Qt6) widgets — main window, track list, playback bar
- **Audio Layer**: FFmpeg subprocess for analysis/processing; QMediaPlayer for playback
- **Data Layer**: Track model with command history for undo/redo
- **Safety**: All file writes use atomic backup + restore on failure

## License

MIT License — see [LICENSE.txt](LICENSE.txt)

Copyright (c) 2026 Sophia Backstein
