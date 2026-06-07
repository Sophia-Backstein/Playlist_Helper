#!/usr/bin/env python3
"""Playlist Helper — Audio file management and processing application.

A desktop application for managing audio files:
- Load audio files from a folder (mp3, m4a, opus, wav)
- Trim audio with a dual-point range slider
- Edit filenames and metadata
- Manage album cover art
- Convert between formats (mp3, wav)
- Analyze and equalize volume
- Safe save with automatic backup
"""

import argparse
import os
import sys

# Ensure the src package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Playlist Helper — Audio file management and processing.",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        default=False,
        help="Run test suite on bundled test samples and exit.",
    )
    parser.add_argument(
        "--limit-per-format",
        type=int,
        default=None,
        metavar="N",
        help="When used with --run-tests, limit to N files per format.",
    )
    return parser.parse_args()


def run_tests(limit_per_format: int | None = None) -> None:
    """Run the test suite with optional file-per-format limit.

    Exits with 0 on all-pass, 1 on any failure.
    """
    from tests.test_all import run_all_tests, setup_active_dir, ACTIVE_DIR
    import shutil

    setup_active_dir()
    try:
        sys.exit(run_all_tests(limit_per_format=limit_per_format))
    finally:
        if os.path.exists(ACTIVE_DIR):
            shutil.rmtree(ACTIVE_DIR)


def main() -> None:
    """Main entry point.

    Dispatches to test mode or GUI mode based on CLI args.
    """
    args = parse_args()

    if args.run_tests:
        run_tests(limit_per_format=args.limit_per_format)
        return

    from src.app import run

    run()


if __name__ == "__main__":
    main()
