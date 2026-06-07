"""File operations for safe saving with backup."""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Optional


def ensure_backup_dir(file_path: str) -> str:
    """Ensure a .backup directory exists next to the file.
    
    Args:
        file_path: Path to the original file.
        
    Returns:
        Path to the .backup directory.
    """
    parent = os.path.dirname(os.path.abspath(file_path))
    backup_dir = os.path.join(parent, ".backup")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def save_with_backup(temp_path: str, original_path: str) -> Optional[str]:
    """Safely save by replacing the original file with a temp file.
    
    Process:
    1. Ensure the original file handle is closed (caller's responsibility).
    2. Create .backup folder if needed.
    3. Move original file to .backup/.
    4. Copy temp file to original path.
    5. Remove temp file.
    
    Args:
        temp_path: Path to the temporary processed file.
        original_path: Path to the original file to replace.
        
    Returns:
        Path to the backup file (if one was created), or None if no backup
        was made (e.g., original didn't exist).
        
    Raises:
        FileNotFoundError: If temp_path doesn't exist.
        OSError: On file operation failures.
    """
    original_path = os.path.abspath(original_path)
    temp_path = os.path.abspath(temp_path)
    
    if not os.path.exists(temp_path):
        raise FileNotFoundError(f"Temporary file not found: {temp_path}")
    
    if not os.path.exists(original_path):
        # No original to backup — just move temp to original
        shutil.move(temp_path, original_path)
        return None
    
    backup_dir = ensure_backup_dir(original_path)
    original_basename = os.path.basename(original_path)
    backup_path = os.path.join(backup_dir, original_basename)
    
    # Handle backup name collision by appending a timestamp
    if os.path.exists(backup_path):
        stem, ext = os.path.splitext(original_basename)
        timestamp = int(__import__("time").time())
        backup_path = os.path.join(backup_dir, f"{stem}_{timestamp}{ext}")
    
    # Move original to backup
    shutil.move(original_path, backup_path)
    
    try:
        # Try atomic replace (works only when temp + original are on same filesystem)
        os.replace(temp_path, original_path)
    except OSError:
        # Fallback for cross-filesystem (e.g., /tmp on tmpfs vs /home on ext4):
        # use copy + manual remove instead
        try:
            shutil.copy2(temp_path, original_path)
            os.remove(temp_path)
        except Exception:
            # Restore from backup on failure
            shutil.move(backup_path, original_path)
            raise
    except Exception:
        # Non-OSError: restore from backup
        shutil.move(backup_path, original_path)
        raise
    finally:
        # Ensure temp is cleaned up
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
    
    return backup_path


def create_temp_file(suffix: str = "") -> str:
    """Create a temporary file path.
    
    Args:
        suffix: File suffix (e.g., '.mp3').
        
    Returns:
        Path to the temporary file.
    """
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path
