#!/usr/bin/env python3
"""Build script for creating Windows .exe using PyInstaller.

Usage:
    python build_exe.py              # Build .exe
    python build_exe.py --onefile    # Build single-file .exe

Requirements:
    pip install pyinstaller
"""

import os
import sys
import subprocess
import shutil


def build_exe(onefile: bool = True) -> None:
    """Build the Windows executable using PyInstaller.
    
    Args:
        onefile: If True, create a single .exe file.
    """
    # Ensure we're in the project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Check that PyInstaller is available (in current venv or system PATH)
    pyinstaller_path = shutil.which("pyinstaller")
    if not pyinstaller_path:
        # Check in the same directory as the running Python
        python_dir = os.path.dirname(sys.executable)
        venv_pyinstaller = os.path.join(python_dir, "pyinstaller")
        if os.path.exists(venv_pyinstaller):
            pyinstaller_path = venv_pyinstaller
    if not pyinstaller_path:
        print("ERROR: PyInstaller not found. Install with: pip install pyinstaller")
        sys.exit(1)
    
    # Ensure ffmpeg is bundled (note: for distribution, bundle ffmpeg.exe separately)
    
    args = [
        pyinstaller_path,
        "--name", "PlaylistHelper",
        "--windowed",  # No console window
        "--add-data", f"src{os.pathsep}src",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "PySide6.QtWidgets",
        "--clean",
        "--noconfirm",
    ]
    
    if os.path.exists("resources/icon.ico"):
        args.insert(3, "resources/icon.ico")
        args.insert(3, "--icon")
    
    if onefile:
        args.append("--onefile")
    else:
        args.append("--onedir")
    
    args.append("main.py")
    
    print("Building PlaylistHelper executable...")
    print(f"Command: {' '.join(args)}")
    
    result = subprocess.run(args)
    
    if result.returncode == 0:
        print("\n✅ Build successful!")
        # PyInstaller output name varies by platform
        exe_name = "PlaylistHelper.exe" if sys.platform == "win32" else "PlaylistHelper"
        if onefile:
            exe_path = os.path.join("dist", exe_name)
        else:
            exe_path = os.path.join("dist", "PlaylistHelper", exe_name)
        
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"   Executable: {exe_path}")
            print(f"   Size: {size_mb:.1f} MB")
        
        print("\nNOTE: FFmpeg must be installed separately on the target system,")
        print("or bundled alongside the executable. Users on Windows can")
        print("download ffmpeg from https://ffmpeg.org/download.html")
    else:
        print("\n❌ Build failed!")
        sys.exit(1)


if __name__ == "__main__":
    onefile = "--onefile" in sys.argv or "-1" in sys.argv
    build_exe(onefile=onefile)
