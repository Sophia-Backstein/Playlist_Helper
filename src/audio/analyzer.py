"""Volume analysis and cleaned average calculation."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import struct
import tempfile
from typing import Dict, List, Optional


def analyze_volume_ffmpeg(file_path: str) -> Dict[str, float]:
    """Analyze audio volume using FFmpeg's volumedetect filter.
    
    Args:
        file_path: Path to audio file.
        
    Returns:
        Dict with keys: 'mean_volume', 'max_volume' (both in dB).
        Returns zero values on failure.
    """
    result: Dict[str, float] = {
        "mean_volume": 0.0,
        "max_volume": 0.0,
    }
    
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-v", "info",
                "-i", file_path,
                "-af", "volumedetect",
                "-f", "null", "-",
            ],
            capture_output=True, text=True, timeout=120,
        )
        
        stderr = proc.stderr
        
        # Parse mean_volume
        match = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", stderr)
        if match:
            result["mean_volume"] = float(match.group(1))
        
        # Parse max_volume
        match = re.search(r"max_volume:\s*([-\d.]+)\s*dB", stderr)
        if match:
            result["max_volume"] = float(match.group(1))
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return result


def compute_cleaned_average(file_path: str) -> float:
    """Compute the cleaned average volume.
    
    Extracts raw PCM samples, sorts them, discards the quietest 10%
    and loudest 10%, and averages the middle 80%.
    
    Args:
        file_path: Path to audio file.
        
    Returns:
        Cleaned average volume in dB, or 0.0 on failure.
    """
    samples = _get_raw_samples(file_path)
    if not samples:
        return 0.0
    
    samples.sort()
    n = len(samples)
    start_idx = int(n * 0.1)
    end_idx = int(n * 0.9)
    
    if end_idx <= start_idx:
        return 0.0
    
    middle = samples[start_idx:end_idx]
    if not middle:
        return 0.0
    
    # Compute RMS of middle samples
    rms = (sum(s * s for s in middle) / len(middle)) ** 0.5
    if rms <= 0:
        return 0.0
    
    db = 20.0 * math.log10(rms)
    return round(db, 2)


def _get_raw_samples(file_path: str, max_duration: float = 30.0) -> List[float]:
    """Extract raw audio samples as float values.
    
    Uses FFmpeg to decode audio to 16-bit PCM, reads samples,
    and returns them as normalized float values in [-1.0, 1.0].
    
    Args:
        file_path: Path to audio file.
        max_duration: Maximum duration to analyze in seconds.
            Uses first N seconds for efficiency. Set to 0 for full file.
        
    Returns:
        List of float sample values.
    """
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    
    try:
        # First get duration to decide how much to read
        duration_cmd = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", file_path],
            capture_output=True, text=True, timeout=15,
        )
        duration = 0.0
        try:
            info = json.loads(duration_cmd.stdout)
            duration = float(info.get("format", {}).get("duration", 0))
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        
        # We only analyze up to max_duration or the actual duration
        analyze_duration = min(duration, max_duration) if duration > 0 else max_duration
        
        # Convert to mono WAV for analysis (take first 30s max)
        convert_args = [
            "ffmpeg", "-y", "-v", "quiet",
            "-i", file_path,
            "-t", str(analyze_duration),
            "-ac", "1",       # mono
            "-ar", "22050",   # 22kHz sample rate — good enough for volume
            "-f", "wav",
            "-bitexact",
            wav_path,
        ]
        
        result = subprocess.run(
            convert_args, capture_output=True, timeout=120,
        )
        
        if result.returncode != 0 or not os.path.exists(wav_path):
            return []
        
        # Read the WAV file and extract samples
        with open(wav_path, "rb") as f:
            raw = f.read()
        
        # Skip WAV header (44 bytes for standard PCM WAV)
        header_size = 44
        if len(raw) <= header_size:
            return []
        
        pcm_data = raw[header_size:]
        
        # Decode as 16-bit signed little-endian PCM
        sample_count = len(pcm_data) // 2
        samples: List[float] = []
        
        # To avoid overwhelming memory, subsample if too many samples
        # Target: ~100k samples for analysis
        target_samples = 100000
        step = max(1, sample_count // target_samples)
        
        for i in range(0, sample_count, step):
            offset = i * 2
            if offset + 2 > len(pcm_data):
                break
            sample = struct.unpack_from("<h", pcm_data, offset)[0]
            samples.append(sample / 32768.0)
        
        return samples
        
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


def compute_loudest_average(file_path: str) -> float:
    """Compute the average volume considering loudest samples.
    
    Uses the top 50% loudest samples for the average.
    
    Args:
        file_path: Path to audio file.
        
    Returns:
        Loudest-biased average in dB.
    """
    samples = _get_raw_samples(file_path)
    if not samples:
        return 0.0
    
    samples.sort()
    n = len(samples)
    start_idx = int(n * 0.5)  # Top 50%
    
    if start_idx >= n:
        return 0.0
    
    loudest = samples[start_idx:]
    
    rms = (sum(s * s for s in loudest) / len(loudest)) ** 0.5
    if rms <= 0:
        return 0.0
    
    db = 20.0 * math.log10(rms)
    return round(db, 2)
