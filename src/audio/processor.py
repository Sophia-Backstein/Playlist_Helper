"""Audio processing operations: trimming, format conversion."""

from __future__ import annotations

import os
import subprocess
from typing import Optional


def trim_audio(
    input_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
) -> bool:
    """Trim audio to a specified time range.

    Re-encodes audio for accurate trimming (stream copy is not
    frame-accurate across all formats). Output format matches input.

    Args:
        input_path: Path to input audio file.
        output_path: Path for output file.
        start_time: Start time in seconds.
        end_time: End time in seconds.

    Returns:
        True if successful.
    """
    if end_time <= start_time:
        return False

    # Choose codec based on output extension
    out_ext = os.path.splitext(output_path)[1].lower()
    if out_ext == ".mp3":
        codec_args = ["-c:a", "libmp3lame", "-q:a", "2"]
    elif out_ext == ".wav":
        codec_args = ["-c:a", "pcm_s16le"]
    elif out_ext == ".flac":
        codec_args = ["-c:a", "flac"]
    elif out_ext == ".opus":
        codec_args = ["-c:a", "libopus"]
    elif out_ext == ".m4a":
        codec_args = ["-c:a", "aac"]
    else:
        codec_args = ["-c:a", "libmp3lame", "-q:a", "2"]

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-i", input_path,
                "-ss", str(start_time),
                "-to", str(end_time),
                *codec_args,
                output_path,
            ],
            capture_output=True, timeout=120,
        )
        return result.returncode == 0 and os.path.getsize(output_path) > 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def convert_format(
    input_path: str,
    output_path: str,
    target_format: str,
) -> bool:
    """Convert audio to a different format.
    
    Args:
        input_path: Path to input audio file.
        output_path: Path for output file.
        target_format: "mp3", "wav", or "flac".
        
    Returns:
        True if successful.
    """
    try:
        if target_format == "mp3":
            codec_args = ["-c:a", "libmp3lame", "-q:a", "2"]
        elif target_format == "wav":
            codec_args = ["-c:a", "pcm_s16le"]
        elif target_format == "flac":
            codec_args = ["-c:a", "flac"]
        else:
            return False
        
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-i", input_path,
                *codec_args,
                output_path,
            ],
            capture_output=True, timeout=300,
        )
        return result.returncode == 0 and os.path.getsize(output_path) > 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def process_and_convert(
    input_path: str,
    output_path: str,
    target_format: str,
    start_time: float = 0.0,
    end_time: Optional[float] = None,
    volume_gain_db: Optional[float] = None,
) -> bool:
    """Process audio: trim + convert + volume in one FFmpeg pass.
    
    Combines trimming, format conversion, and volume adjustment
    in a single FFmpeg call for efficiency.
    
    Args:
        input_path: Path to input audio file.
        output_path: Path for output file.
        target_format: "mp3", "wav", or "flac".
        start_time: Trim start in seconds.
        end_time: Trim end in seconds (None = use full file).
        volume_gain_db: Volume adjustment in dB (None = no adjustment).
        
    Returns:
        True if successful.
    """
    try:
        # Build filter chain
        filter_parts = []
        
        # Volume adjustment
        if volume_gain_db is not None and volume_gain_db != 0.0:
            filter_parts.append(f"volume={volume_gain_db}dB")
        
        filter_chain = ",".join(filter_parts) if filter_parts else None
        
        # Build command
        cmd = ["ffmpeg", "-y", "-v", "quiet"]
        
        # Input
        cmd.extend(["-i", input_path])
        
        # Trim
        cmd.extend(["-ss", str(start_time)])
        if end_time is not None:
            cmd.extend(["-to", str(end_time)])
        
        # Filter
        if filter_chain:
            cmd.extend(["-af", filter_chain])
        
        # Output codec
        if target_format == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-q:a", "2"])
        elif target_format == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif target_format == "flac":
            cmd.extend(["-c:a", "flac"])
        else:
            return False
        
        cmd.append(output_path)
        
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        
        if result.returncode != 0 or not os.path.exists(output_path):
            return False
        return os.path.getsize(output_path) > 0
        
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
