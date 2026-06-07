#!/usr/bin/env python3
"""Setup script for Playlist Helper."""

from setuptools import setup, find_packages

setup(
    name="playlist-helper",
    version="1.0.0",
    description="Audio file management and processing application",
    long_description="A desktop application for managing audio files: load, trim, edit metadata, manage cover art, convert formats, analyze and equalize volume, safe save with automatic backup.",
    long_description_content_type="text/plain",
    author="PlaylistHelper",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "PySide6>=6.6.0",
    ],
    entry_points={
        "console_scripts": [
            "playlist-helper=main:main",
        ],
    },
    python_requires=">=3.10",
)
