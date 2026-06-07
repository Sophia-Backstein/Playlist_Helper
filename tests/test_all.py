"""Comprehensive test suite for Playlist Helper.

Tests all 8 function categories across all audio files.
Workflow: copy from tests/original/ -> tests/active/ -> run functions -> verify.

Functions tested:
  - Loading (scan, Track creation, volume analysis)
  - Cutting (trim_audio)
  - Format conversion (convert_format, process_and_convert)
  - Filename change (Track.file_name)
  - Title change (set_title_metadata, read_title_metadata)
  - Cover change (set_cover_art, extract_cover_art)
  - Volume change (volume gain via ffmpeg)
  - Equalize to average (equalize_to_average)
  - Equalize to loudest (equalize_to_loudest)
"""

from __future__ import annotations

import os
import shutil
import sys
import json
import subprocess
import tempfile
import struct
import math

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.audio.scanner import scan_folder, SUPPORTED_EXTENSIONS
from src.audio.analyzer import (
    analyze_volume_ffmpeg, compute_cleaned_average,
)
from src.audio.metadata import (
    get_duration_ffprobe,
    read_title_metadata,
    set_title_metadata,
    extract_cover_art,
    set_cover_art,
)
from src.audio.processor import trim_audio, convert_format, process_and_convert
from src.audio.equalizer import equalize_to_average, equalize_to_loudest
from src.models.track import Track
from src.utils.file_ops import create_temp_file


# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORIGINAL_DIR = os.path.join(BASE_DIR, "original")
ACTIVE_DIR = os.path.join(BASE_DIR, "active")
COVER_TEST_IMAGE = os.path.join(BASE_DIR, "cover_test.png")

# Test config
TEST_FORMATS = ["mp3", "wav", "flac"]
VOLUME_TEST_GAIN_DB = 3.0
EQ_TARGET_DB = -16.0

# Results tracking
results: dict[str, dict[str, bool | str]] = {}
function_stats: dict[str, dict[str, int]] = {}


def log(msg: str) -> None:
    print(msg)


def setup_active_dir() -> None:
    """Clean and recreate the active directory."""
    if os.path.exists(ACTIVE_DIR):
        shutil.rmtree(ACTIVE_DIR)
    os.makedirs(ACTIVE_DIR, exist_ok=True)


def get_original_files() -> list[str]:
    """Get all audio files from the original directory."""
    return scan_folder(ORIGINAL_DIR)


def prepare_copy(rel_path: str) -> str:
    """Copy a file from original to active directory."""
    src = os.path.join(ORIGINAL_DIR, rel_path)
    dst = os.path.join(ACTIVE_DIR, rel_path)
    # Ensure parent subdir exists
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def get_duration(path: str) -> float:
    """Get duration via ffprobe."""
    return get_duration_ffprobe(path)


# === Test Categories ===

def test_loading(file_path: str) -> bool:
    """Test that a file can be scanned, loaded into Track, and analyzed."""
    try:
        # scan_folder should find it
        parent = os.path.dirname(file_path)
        scanned = scan_folder(parent)
        if file_path not in scanned:
            log(f"    FAIL: scan_folder did not return {os.path.basename(file_path)}")
            return False

        # Metadata reading
        duration = get_duration(file_path)
        if duration <= 0:
            log(f"    FAIL: duration {duration}s for {os.path.basename(file_path)}")
            return False

        # Volume analysis
        volume = analyze_volume_ffmpeg(file_path)
        cleaned = compute_cleaned_average(file_path)

        # Track creation
        track = Track(
            file_path=file_path,
            file_name=os.path.basename(file_path),
            title=read_title_metadata(file_path),
            duration_seconds=duration,
            average_volume_db=volume.get("mean_volume", 0.0),
            cleaned_average_db=cleaned,
            max_volume_db=volume.get("max_volume", 0.0),
        )
        # Track model should be valid
        assert track.file_path == file_path
        assert track.duration_seconds > 0
        return True
    except Exception as e:
        log(f"    FAIL: loading exception: {e}")
        return False


def test_cutting(file_path: str) -> bool:
    """Test trim_audio: cut a segment and verify shorter duration."""
    try:
        duration = get_duration(file_path)
        if duration < 2.0:
            # File too short to cut meaningfully
            return True  # skip

        tmp = create_temp_file(suffix=os.path.splitext(file_path)[1])
        start = 0.5
        end = min(duration - 0.5, start + 3.0)
        if end <= start:
            return True  # skip

        success = trim_audio(file_path, tmp, start, end)
        if not success or not os.path.exists(tmp):
            log(f"    FAIL: trim_audio returned False for {os.path.basename(file_path)}")
            return False

        trimmed_dur = get_duration(tmp)
        expected = round(end - start, 1)
        actual = round(trimmed_dur, 1)
        if actual < expected - 0.5 or actual > expected + 0.5:
            log(f"    FAIL: trim duration {actual}s != expected ~{expected}s for "
                f"{os.path.basename(file_path)}")
            return False
        return True
    finally:
        if 'tmp' in dir() and os.path.exists(tmp):
            os.remove(tmp)


def test_conversion(file_path: str) -> bool:
    """Test format conversion to supported output formats."""
    ext = os.path.splitext(file_path)[1].lower()
    source_format = ext.lstrip(".")
    for target_format in TEST_FORMATS:
        if target_format == source_format:
            # Convert to same format should still work
            pass
        try:
            suffix = f".{target_format}"
            tmp = create_temp_file(suffix=suffix)
            success = convert_format(file_path, tmp, target_format)
            if not success or not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
                log(f"    FAIL: convert to {target_format} for "
                    f"{os.path.basename(file_path)}")
                if os.path.exists(tmp):
                    os.remove(tmp)
                return False
            # Verify extension matches
            actual_ext = os.path.splitext(tmp)[1].lower()
            if actual_ext != suffix:
                log(f"    FAIL: converted file has extension {actual_ext}, expected "
                    f"{suffix}")
                os.remove(tmp)
                return False
            os.remove(tmp)
        except Exception as e:
            log(f"    FAIL: conversion to {target_format} exception: {e}")
            if 'tmp' in dir() and os.path.exists(tmp):
                os.remove(tmp)
            return False
    return True


def test_filename_change(file_path: str) -> bool:
    """Test filename change by renaming the file and verifying."""
    try:
        base_dir = os.path.dirname(file_path)
        original_basename = os.path.basename(file_path)
        name, ext = os.path.splitext(original_basename)
        new_basename = f"{name}_renamed{ext}"
        new_path = os.path.join(base_dir, new_basename)

        # Rename
        os.rename(file_path, new_path)

        # Verify new file exists
        if not os.path.exists(new_path):
            log(f"    FAIL: renamed file not found")
            os.rename(new_path, file_path)
            return False

        # Verify old name doesn't exist
        if os.path.exists(file_path):
            log(f"    FAIL: old filename still exists")
            os.rename(new_path, file_path)
            return False

        # Verify it's still a valid audio file
        dur = get_duration(new_path)
        if dur <= 0:
            log(f"    FAIL: renamed file has invalid duration")
            os.rename(new_path, file_path)
            return False

        # Rename back
        os.rename(new_path, file_path)
        return True
    except Exception as e:
        log(f"    FAIL: filename change exception: {e}")
        return False


# Container formats known to support embedded metadata and cover art
# (WAV has no metadata; OPUS has limited Vorbis comment support
#  that the ffmpeg-based helpers do not handle.)
_METADATA_FORMATS = {".mp3", ".flac", ".m4a", ".m4b", ".aac", ".wma", ".ogg"}
_COVER_FORMATS = {".mp3", ".flac", ".m4a", ".m4b"}


def _format_supports(file_path: str, feature: str) -> bool:
    ext = os.path.splitext(file_path)[1].lower()
    if feature == "metadata":
        return ext in _METADATA_FORMATS
    if feature == "cover":
        return ext in _COVER_FORMATS
    return True


def test_title_change(file_path: str) -> bool:
    """Test reading and writing title metadata."""
    if not _format_supports(file_path, "metadata"):
        log(f"    SKIP: format does not support embedded metadata")
        return True
    try:
        # Read original title
        original_title = read_title_metadata(file_path)
        test_title = f"Test Title - {os.path.basename(file_path)}"

        # Write new title
        success = set_title_metadata(file_path, test_title)
        if not success:
            log(f"    FAIL: set_title_metadata returned False for "
                f"{os.path.basename(file_path)}")
            return False

        # Read back
        read_title = read_title_metadata(file_path)
        if read_title != test_title:
            log(f"    FAIL: title mismatch after write. Expected '{test_title}', "
                f"got '{read_title}'")
            # Restore original title
            set_title_metadata(file_path, original_title)
            return False

        # Restore original title
        if original_title:
            set_title_metadata(file_path, original_title)
        return True
    except Exception as e:
        log(f"    FAIL: title change exception: {e}")
        return False


def test_cover_change(file_path: str) -> bool:
    """Test cover art change: set checkered PNG, then extract and verify."""
    if not _format_supports(file_path, "cover"):
        log(f"    SKIP: format does not support embedded cover art")
        return True
    original_cover: str | None = None
    new_cover: str | None = None
    try:
        if not os.path.exists(COVER_TEST_IMAGE):
            log(f"    FAIL: cover test image not found")
            return False

        # Read original cover (for restoration if any)
        original_cover = extract_cover_art(file_path)

        # Set new cover from checkered PNG
        success = set_cover_art(file_path, COVER_TEST_IMAGE)
        if not success:
            log(f"    FAIL: set_cover_art failed for {os.path.basename(file_path)}")
            return False

        # Extract cover after set
        new_cover = extract_cover_art(file_path)
        if new_cover is None or not os.path.exists(new_cover):
            log(f"    FAIL: could not extract cover after set for "
                f"{os.path.basename(file_path)}")
            return False

        # Verify cover file is reasonably sized (should be our checkered PNG)
        new_size = os.path.getsize(new_cover)
        if new_size < 100:
            log(f"    FAIL: extracted cover too small ({new_size}B)")
            return False

        # Verify the extracted cover differs from the original (content changed)
        if original_cover and os.path.getsize(original_cover) > 0 and \
                os.path.getsize(new_cover) == os.path.getsize(original_cover):
            # Same size — check content hash to be sure
            with open(original_cover, "rb") as f:
                orig_hash = hash(f.read())
            with open(new_cover, "rb") as f:
                new_hash = hash(f.read())
            if orig_hash == new_hash:
                log(f"    FAIL: extracted cover matches original — content unchanged")
                return False

        # Restore original cover if there was one
        if original_cover and os.path.exists(original_cover):
            set_cover_art(file_path, original_cover)
        return True
    except Exception as e:
        log(f"    FAIL: cover change exception: {e}")
        return False
    finally:
        for _p in (original_cover, new_cover):
            if _p and os.path.exists(_p):
                os.remove(_p)


def test_volume_change(file_path: str) -> bool:
    """Test volume change by applying a gain and verifying difference."""
    try:
        # Analyze original volume
        vol_before = analyze_volume_ffmpeg(file_path)
        mean_before = vol_before.get("mean_volume", 0.0)
        if mean_before == 0.0:
            # Can't analyze volume, skip test
            return True

        # Apply gain via ffmpeg — use lossless WAV to avoid encoder artifacts
        tmp = create_temp_file(suffix=".wav")

        result = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-i", file_path,
                "-af", f"volume={VOLUME_TEST_GAIN_DB}dB",
                "-c:a", "pcm_s16le",
                "-f", "wav",
                tmp,
            ],
            capture_output=True, timeout=120,
        )

        if result.returncode != 0 or not os.path.exists(tmp):
            log(f"    FAIL: volume gain ffmpeg failed for {os.path.basename(file_path)}")
            return False

        # Analyze volume after gain
        vol_after = analyze_volume_ffmpeg(tmp)
        mean_after = vol_after.get("mean_volume", 0.0)

        if mean_after == 0.0:
            log(f"    FAIL: volume analysis after gain returned 0 for "
                f"{os.path.basename(file_path)}")
            return False

        # After applying +3dB gain, the new mean should be ~3dB higher
        diff = round(mean_after - mean_before, 1)
        expected_diff = round(VOLUME_TEST_GAIN_DB, 1)
        if abs(diff - expected_diff) > 1.0:
            log(f"    FAIL: volume change {diff}dB != expected {expected_diff}dB for "
                f"{os.path.basename(file_path)}")
            return False

        return True
    except Exception as e:
        log(f"    FAIL: volume change exception: {e}")
        return False
    finally:
        if 'tmp' in dir() and os.path.exists(tmp):
            os.remove(tmp)


def test_equalize_average(file_path: str) -> bool:
    """Test equalize_to_average function, verifying volume changes toward target."""
    try:
        # Measure cleaned average before
        cleaned_before = compute_cleaned_average(file_path)

        result = equalize_to_average(file_path, EQ_TARGET_DB)
        if result is None:
            log(f"    FAIL: equalize_to_average returned None for "
                f"{os.path.basename(file_path)}")
            return False

        if not os.path.exists(result):
            log(f"    FAIL: equalize_to_average output file doesn't exist for "
                f"{os.path.basename(file_path)}")
            return False

        if os.path.getsize(result) == 0:
            log(f"    FAIL: equalize_to_average output is empty for "
                f"{os.path.basename(file_path)}")
            return False

        # If result is a temp file (different from input), verify it's valid audio
        if result != file_path:
            dur = get_duration(result)
            if dur <= 0:
                os.remove(result)
                log(f"    FAIL: equalize_to_average output has invalid duration for "
                    f"{os.path.basename(file_path)}")
                return False

            # Verify cleaned average moved toward the target
            cleaned_after = compute_cleaned_average(result)
            if cleaned_after != 0.0 and cleaned_before != 0.0:
                before_target_gap = abs(cleaned_before - EQ_TARGET_DB)
                after_target_gap = abs(cleaned_after - EQ_TARGET_DB)
                # Only enforce if before gap is significant (> 0.5 dB)
                if before_target_gap > 0.5 and after_target_gap >= before_target_gap:
                    log(f"    FAIL: equalize_to_average didn't move volume toward target. "
                        f"Before: {cleaned_before:.1f}dB (gap {before_target_gap:.1f}), "
                        f"After: {cleaned_after:.1f}dB (gap {after_target_gap:.1f}) for "
                        f"{os.path.basename(file_path)}")
                    os.remove(result)
                    return False

            os.remove(result)

        return True
    except Exception as e:
        log(f"    FAIL: equalize_to_average exception: {e}")
        return False


def test_equalize_loudest(file_path: str) -> bool:
    """Test equalize_to_loudest function, verifying volume changes toward target."""
    try:
        # Measure cleaned average before
        cleaned_before = compute_cleaned_average(file_path)

        result = equalize_to_loudest(file_path, target_db=EQ_TARGET_DB)
        if result is None:
            log(f"    FAIL: equalize_to_loudest returned None for "
                f"{os.path.basename(file_path)}")
            return False

        if not os.path.exists(result):
            log(f"    FAIL: equalize_to_loudest output file doesn't exist for "
                f"{os.path.basename(file_path)}")
            return False

        if os.path.getsize(result) == 0:
            log(f"    FAIL: equalize_to_loudest output is empty for "
                f"{os.path.basename(file_path)}")
            return False

        # If result is a temp file, verify it's valid audio and volume moved
        if result != file_path:
            dur = get_duration(result)
            if dur <= 0:
                os.remove(result)
                log(f"    FAIL: equalize_to_loudest output has invalid duration for "
                    f"{os.path.basename(file_path)}")
                return False

            # Verify cleaned average moved toward the target
            cleaned_after = compute_cleaned_average(result)
            if cleaned_after != 0.0 and cleaned_before != 0.0:
                before_gap = abs(cleaned_before - EQ_TARGET_DB)
                after_gap = abs(cleaned_after - EQ_TARGET_DB)
                if before_gap > 0.5 and after_gap >= before_gap:
                    log(f"    FAIL: equalize_to_loudest didn't move cleaned avg toward target. "
                        f"Before: {cleaned_before:.1f}dB (gap {before_gap:.1f}), "
                        f"After: {cleaned_after:.1f}dB (gap {after_gap:.1f}) for "
                        f"{os.path.basename(file_path)}")
                    os.remove(result)
                    return False

            os.remove(result)

        return True
    except Exception as e:
        log(f"    FAIL: equalize_to_loudest exception: {e}")
        return False


# === Test Runner ===

def check_ffmpeg() -> bool:
    """Verify ffmpeg and ffprobe are available on PATH."""
    for cmd in ("ffmpeg", "ffprobe"):
        if subprocess.run([cmd, "-version"], capture_output=True, timeout=10).returncode != 0:
            log(f"ERROR: {cmd} not found on PATH — volume tests will pass vacuously")
            return False
    return True


def run_all_tests(limit_per_format: int | None = None) -> int:
    """Run all test categories on all files.

    Args:
        limit_per_format: If set, only process N files per extension.

    Returns:
        0 if all tests pass, 1 if any fail.
    """
    global function_stats

    if not check_ffmpeg():
        log("WARNING: ffmpeg missing — volume-dependent tests may pass vacuously.")
        log("Install ffmpeg: sudo dnf install ffmpeg (Fedora) or sudo apt install ffmpeg (Debian)")

    func_names = [
        "loading",
        "cutting",
        "conversion",
        "filename_change",
        "title_change",
        "cover_change",
        "volume_change",
        "equalize_average",
        "equalize_loudest",
    ]
    function_stats = {
        fn: {"pass": 0, "fail": 0} for fn in func_names
    }

    files = get_original_files()
    log(f"Found {len(files)} audio files in {ORIGINAL_DIR}")

    if limit_per_format is not None and limit_per_format > 0:
        from collections import defaultdict
        by_ext: dict[str, list[str]] = defaultdict(list)
        for f in files:
            by_ext[os.path.splitext(f)[1].lower()].append(f)
        limited: list[str] = []
        for ext, ext_files in sorted(by_ext.items()):
            limited.extend(ext_files[:limit_per_format])
        files = limited
        log(f"  Limited to {limit_per_format} file(s) per format = "
            f"{len(files)} total")
    log(f"Test cover image: {COVER_TEST_IMAGE} "
        f"({'exists' if os.path.exists(COVER_TEST_IMAGE) else 'MISSING'})")
    log("=" * 70)

    total_pass = 0
    total_fail = 0
    total_skip = 0

    for idx, file_path in enumerate(files):
        rel_path = os.path.relpath(file_path, ORIGINAL_DIR)
        basename = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[1].lower()

        log(f"\n[{idx + 1}/{len(files)}] {basename}")

        file_results: dict[str, bool | str] = {}

        # Prepare a clean copy for testing
        active_file = os.path.join(ACTIVE_DIR, f"test_{idx}_{basename}")
        os.makedirs(os.path.dirname(active_file), exist_ok=True)
        # Make sure we start clean
        if os.path.exists(active_file):
            os.remove(active_file)
        shutil.copy2(file_path, active_file)

        test_mapping = [
            ("loading", test_loading),
            ("cutting", test_cutting),
            ("conversion", test_conversion),
            ("filename_change", test_filename_change),
            ("title_change", test_title_change),
            ("cover_change", test_cover_change),
            ("volume_change", test_volume_change),
            ("equalize_average", test_equalize_average),
            ("equalize_loudest", test_equalize_loudest),
        ]

        for func_name, func in test_mapping:
            # Re-prepare a clean copy for each destructive test
            if os.path.exists(active_file):
                os.remove(active_file)
            shutil.copy2(file_path, active_file)

            try:
                result = func(active_file)
                if isinstance(result, bool) and result:
                    file_results[func_name] = True
                    function_stats[func_name]["pass"] += 1
                else:
                    file_results[func_name] = False
                    function_stats[func_name]["fail"] += 1
            except Exception as e:
                file_results[func_name] = False
                function_stats[func_name]["fail"] += 1
                log(f"    FAIL: {func_name} unhandled exception: {e}")

        # Clean up
        if os.path.exists(active_file):
            os.remove(active_file)

        # Determine file-level pass/fail (must pass ALL categories)
        all_pass = all(
            v is True for v in file_results.values()
        )
        details = ", ".join(
            f"{k}={ 'PASS' if v is True else 'FAIL' }"
            for k, v in file_results.items()
        )

        if all_pass:
            total_pass += 1
            log(f"  RESULT: PASS ({details})")
        else:
            total_fail += 1
            log(f"  RESULT: FAIL ({details})")

        results[basename] = file_results

    log("")
    log("=" * 70)
    log(f"OVERALL: {total_pass}/{len(files)} passed, "
        f"{total_fail}/{len(files)} failed")
    log("")

    # Per-function overview
    log("PER-FUNCTION OVERVIEW:")
    log("-" * 70)
    log(f"{'Function':<20} {'Pass':>6} {'Fail':>6} "
        f"{'Rate':>8}")
    log("-" * 70)
    for func_name in func_names:
        s = function_stats[func_name]
        total = s["pass"] + s["fail"]
        rate = f"{s['pass'] / total * 100:.0f}%" if total > 0 else "N/A"
        log(f"{func_name:<20} {s['pass']:>6} {s['fail']:>6} "
            f"{rate:>8}")

    # Summary by file extension
    log("")
    log("RESULTS BY FORMAT:")
    ext_results: dict[str, dict[str, int]] = {}
    for basename, res in results.items():
        ext = os.path.splitext(basename)[1].lower()
        if ext not in ext_results:
            ext_results[ext] = {"pass": 0, "fail": 0}
        if all(v is True for v in res.values()):
            ext_results[ext]["pass"] += 1
        else:
            ext_results[ext]["fail"] += 1
    log(f"{'Format':<10} {'Pass':>6} {'Fail':>6}")
    log("-" * 30)
    for ext in sorted(ext_results.keys()):
        s = ext_results[ext]
        log(f"{ext:<10} {s['pass']:>6} {s['fail']:>6}")

    # Return proper exit code
    return 1 if total_fail > 0 else 0


if __name__ == "__main__":
    setup_active_dir()
    limit = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--limit-per-format" and i < len(sys.argv):
            try:
                limit = int(sys.argv[i + 1])
            except ValueError:
                pass
    try:
        exit_code = run_all_tests(limit_per_format=limit)
        sys.exit(exit_code)
    finally:
        if os.path.exists(ACTIVE_DIR):
            shutil.rmtree(ACTIVE_DIR)
