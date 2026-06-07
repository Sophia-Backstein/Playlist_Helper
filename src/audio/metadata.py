"""Audio metadata reading and writing using FFmpeg/FFprobe."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


def get_duration_ffprobe(file_path: str) -> float:
    """Get audio duration in seconds using ffprobe.
    
    Args:
        file_path: Path to audio file.
        
    Returns:
        Duration in seconds as float.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", file_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))
    except (subprocess.TimeoutExpired, json.JSONDecodeError,
            KeyError, ValueError, FileNotFoundError):
        return 0.0


def extract_cover_art(file_path: str) -> Optional[str]:
    """Extract cover art from an audio file to a temporary file.
    
    Uses FFmpeg to extract the first attached picture / video stream.
    
    Args:
        file_path: Path to the audio file.
        
    Returns:
        Path to extracted image file, or None if no cover art found.
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
    os.close(tmp_fd)
    
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-i", file_path,
                "-an", "-vcodec", "copy",
                tmp_path,
            ],
            capture_output=True, timeout=30,
        )
        if result.returncode != 0 or os.path.getsize(tmp_path) == 0:
            os.remove(tmp_path)
            # Try alternative: extract first frame
            tmp_fd2, tmp_path2 = tempfile.mkstemp(suffix=".png")
            os.close(tmp_fd2)
            result2 = subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "quiet",
                    "-i", file_path,
                    "-an", "-vcodec", "png",
                    "-frames:v", "1",
                    tmp_path2,
                ],
                capture_output=True, timeout=30,
            )
            if result2.returncode == 0 and os.path.getsize(tmp_path2) > 0:
                return tmp_path2
            os.remove(tmp_path2)
            return None
        return tmp_path
    except (subprocess.TimeoutExpired, FileNotFoundError):
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return None


def set_cover_art(file_path: str, image_path: str) -> bool:
    """Set cover art on an audio file using FFmpeg.
    
    Args:
        file_path: Path to the audio file (will be modified in place).
        image_path: Path to the cover image.
        
    Returns:
        True if successful.
    """
    tmp_fd, tmp_path = tempfile.mkstemp(
        suffix=os.path.splitext(file_path)[1]
    )
    os.close(tmp_fd)
    
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-i", file_path,
                "-i", image_path,
                "-map", "0:a:0", "-map", "1:v:0",
                "-c", "copy",
                "-metadata:s:v", "title=Album cover",
                "-disposition:v", "attached_pic",
                tmp_path,
            ],
            capture_output=True, timeout=60,
        )
        if result.returncode == 0 and os.path.getsize(tmp_path) > 0:
            try:
                os.replace(tmp_path, file_path)
            except OSError:
                shutil.copy2(tmp_path, file_path)
                os.remove(tmp_path)
            return True
        os.remove(tmp_path)
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


def set_title_metadata(file_path: str, title: str) -> bool:
    """Set the title metadata tag on an audio file.

    Args:
        file_path: Path to the audio file (modified in place).
        title: New title string.

    Returns:
        True if successful.
    """
    tmp_fd, tmp_path = tempfile.mkstemp(
        suffix=os.path.splitext(file_path)[1]
    )
    os.close(tmp_fd)

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-i", file_path,
                "-map", "0",
                "-c", "copy",
                "-metadata", f"title={title}",
                tmp_path,
            ],
            capture_output=True, timeout=60,
        )
        if result.returncode == 0 and os.path.getsize(tmp_path) > 0:
            try:
                os.replace(tmp_path, file_path)
            except OSError:
                shutil.copy2(tmp_path, file_path)
                os.remove(tmp_path)
            return True
        os.remove(tmp_path)
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


def verify_file_duration(
    file_path: str,
    expected_seconds: float,
    tolerance_ratio: float = 0.05,
) -> bool:
    """Verify an audio file's actual duration matches expected duration.

    Uses ffprobe to measure the file, then compares against expected.
    Logs a warning on mismatch.

    Args:
        file_path: Path to the audio file.
        expected_seconds: Expected duration in seconds.
        tolerance_ratio: Allowed deviation as ratio of expected (default 5%).

    Returns:
        True if duration is within tolerance, False otherwise.
    """
    if expected_seconds <= 0:
        return True  # No meaningful comparison

    actual = get_duration_ffprobe(file_path)
    if actual <= 0:
        logger.warning("verify_file_duration: could not measure %s", file_path)
        return False

    diff = abs(actual - expected_seconds)
    max_diff = expected_seconds * tolerance_ratio
    if diff > max_diff:
        logger.error(
            "verify_file_duration: MISMATCH %s — expected=%.1fs actual=%.1fs "
            "diff=%.1fs (%.1f%%)",
            os.path.basename(file_path),
            expected_seconds, actual, diff,
            (diff / expected_seconds) * 100,
        )
        return False

    logger.info(
        "verify_file_duration: OK %s — %.1fs (expected %.1fs)",
        os.path.basename(file_path), actual, expected_seconds,
    )
    return True


def read_title_metadata(file_path: str) -> str:
    """Read the title metadata tag from an audio file.
    
    Args:
        file_path: Path to audio file.
        
    Returns:
        Title string, or empty string if not found.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", file_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout)
        tags = data.get("format", {}).get("tags", {})
        # Try common title tag names
        for key in ("title", "TITLE", "Title"):
            if key in tags:
                return tags[key]
        return ""
    except (subprocess.TimeoutExpired, json.JSONDecodeError,
            FileNotFoundError):
        return ""
