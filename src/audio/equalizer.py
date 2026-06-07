"""Volume equalization for normalizing audio levels."""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Dict, List, Optional

from .analyzer import compute_cleaned_average


def get_gain_for_target(
    current_db: float,
    target_db: float,
) -> float:
    """Calculate gain needed to reach target volume.
    
    Args:
        current_db: Current volume level in dB.
        target_db: Target volume level in dB.
        
    Returns:
        Gain in dB (positive = boost, negative = cut).
    """
    return round(target_db - current_db, 2)


def equalize_to_average(
    file_path: str,
    target_db: float,
    output_path: Optional[str] = None,
) -> Optional[str]:
    """Equalize a single audio file to a target average volume.
    
    Analyzes current volume, computes gain, applies it.
    Output is written to output_path (or a temp file if None).
    
    Args:
        file_path: Path to audio file.
        target_db: Target average volume in dB.
        output_path: Output path (None = temp file).
        
    Returns:
        Path to equalized file, or None on failure.
    """
    if output_path is None:
        fd, output_path = tempfile.mkstemp(
            suffix=os.path.splitext(file_path)[1]
        )
        os.close(fd)
    
    current_db = compute_cleaned_average(file_path)
    
    if current_db == 0.0:
        # Can't analyze anything — just return a copy
        if output_path != file_path:
            import shutil
            shutil.copy2(file_path, output_path)
        return output_path
    
    gain = get_gain_for_target(current_db, target_db)
    
    try:
        ext = file_path.lower()
        if ext.endswith(".mp3"):
            codec = "libmp3lame"
        elif ext.endswith(".wav"):
            codec = "pcm_s16le"
        elif ext.endswith(".opus"):
            codec = "libopus"
        elif ext.endswith(".flac"):
            codec = "flac"
        else:
            codec = "aac"
        
        cmd = [
            "ffmpeg", "-y", "-v", "quiet",
            "-i", file_path,
            "-af", f"volume={gain}dB",
            "-c:a", codec,
            output_path,
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        
        if result.returncode == 0 and os.path.getsize(output_path) > 0:
            return output_path
        
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def equalize_to_loudest(
    file_path: str,
    output_path: Optional[str] = None,
    target_db: Optional[float] = None,
) -> Optional[str]:
    """Equalize audio based on the loudest average volume.
    
    Computes the loudest average (top 50% of samples) and applies gain
    to reach the target. If no target is given, the track is unchanged
    (gain = 0), acting as a no-op pass-through.
    
    Args:
        file_path: Path to audio file.
        output_path: Output path (None = temp file).
        target_db: Target loudest average in dB. If None, copies input.
        
    Returns:
        Path to equalized file, or None on failure.
    """
    if output_path is None:
        fd, output_path = tempfile.mkstemp(
            suffix=os.path.splitext(file_path)[1]
        )
        os.close(fd)
    
    cleaned_avg = compute_cleaned_average(file_path)
    
    if cleaned_avg == 0.0 or target_db is None:
        # Can't analyze or no target — just copy
        import shutil
        shutil.copy2(file_path, output_path)
        return output_path
    
    gain = round(target_db - cleaned_avg, 2)
    
    if gain == 0.0:
        import shutil
        shutil.copy2(file_path, output_path)
        return output_path
    
    try:
        ext = file_path.lower()
        if ext.endswith(".mp3"):
            codec = "libmp3lame"
        elif ext.endswith(".wav"):
            codec = "pcm_s16le"
        elif ext.endswith(".opus"):
            codec = "libopus"
        elif ext.endswith(".flac"):
            codec = "flac"
        else:
            codec = "aac"
        
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-i", file_path,
                "-af", f"volume={gain}dB",
                "-c:a", codec,
                output_path,
            ],
            capture_output=True, timeout=300,
        )
        
        if result.returncode == 0 and os.path.getsize(output_path) > 0:
            return output_path
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def batch_equalize(
    file_paths: List[str],
    target_db: float,
) -> Dict[str, Optional[str]]:
    """Equalize multiple files to the same target volume.
    
    Args:
        file_paths: List of paths to audio files.
        target_db: Target average volume in dB.
        
    Returns:
        Dict mapping input path -> output path (None on failure).
    """
    results: Dict[str, Optional[str]] = {}
    for path in file_paths:
        results[path] = equalize_to_average(path, target_db)
    return results
