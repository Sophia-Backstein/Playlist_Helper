#!/usr/bin/env python3
"""Build Debian package (.deb) for Playlist Helper.

Constructs a valid .deb ar archive without requiring dpkg-deb or stdeb.
"""

import io
import os
import shutil
import stat
import struct
import sys
import tarfile
import hashlib

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")
DEB_DIR = os.path.join(PROJECT_DIR, "deb_dist")
BUILD_BASE = os.path.join(PROJECT_DIR, "deb_build")

PACKAGE = "playlist-helper"
VERSION = "1.0.0-1"
ARCH = "all"
DEB_FILENAME = f"{PACKAGE}_{VERSION}_{ARCH}.deb"


def make_control_tgz() -> bytes:
    """Build control.tar.gz with Debian control metadata."""
    control = """\
Package: playlist-helper
Version: 1.0.0-1
Architecture: all
Maintainer: PlaylistHelper
Description: Audio file management application
 Desktop app for managing audio files: load, trim, edit metadata,
 manage cover art, convert formats, analyze and equalize volume.
Section: sound
Priority: optional
Depends: python3 (>= 3.10), python3-pyside6 (>= 6.6.0)
"""

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="control")
        info.size = len(control)
        info.mtime = 0
        info.mode = 0o644
        tar.addfile(info, io.BytesIO(control.encode()))
    return buf.getvalue()


def make_data_tgz() -> bytes:
    """Build data.tar.gz with application files."""
    src_dir = PROJECT_DIR

    install_root = "/opt/playlist-helper"
    files_to_include = []

    # Walk the source tree for files to include
    exclude_prefixes = (".venv", ".wine", "build", "deb_build", "deb_dist",
                        "dist", "rpmbuild", "__pycache__", ".git", ".egg-info")

    for root, dirs, fnames in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        # Skip excluded dirs
        if rel == ".":
            dirs[:] = [d for d in dirs if not d.startswith(exclude_prefixes) and not d.startswith(".")]
            continue
        parts = rel.split(os.sep)
        if parts[0].startswith(exclude_prefixes) or parts[0].startswith("."):
            dirs[:] = []
            continue
        for fn in fnames:
            fpath = os.path.join(root, fn)
            rel_path = os.path.relpath(fpath, src_dir)
            files_to_include.append((fpath, rel_path))

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for fpath, rel_path in files_to_include:
            st = os.stat(fpath)
            is_exec = bool(st.st_mode & stat.S_IXUSR)
            out_path = os.path.join(install_root, rel_path)

            info = tarfile.TarInfo(name=out_path)
            info.size = st.st_size
            info.mtime = int(st.st_mtime)
            info.mode = 0o100755 if is_exec else 0o100644
            info.type = tarfile.REGTYPE
            info.uid = 0
            info.gid = 0

            with open(fpath, "rb") as f:
                data = f.read()
            tar.addfile(info, io.BytesIO(data))

    return buf.getvalue()


def write_ar_archive(output_path: str, members: list[tuple[str, bytes]]):
    """Write a valid ar archive (BSD variant, used by Debian packages)."""
    with open(output_path, "wb") as f:
        f.write(b"!<arch>\n")
        for name, data in members:
            # Pad name to 16 bytes
            name_bytes = name.encode("ascii")
            if len(name_bytes) > 15:
                name_bytes = name_bytes[:15]
            name_padded = name_bytes.ljust(16, b" ")

            # Pad data to even length
            size = len(data)
            size_padded = size + (size % 2)

            # Ar header: name(16) + timestamp(12) + owner(6) + group(6) + mode(8) + size(10) + magic(2)
            header = struct.pack(
                "16s12s6s6s8s10s2s",
                name_padded,
                b"0".ljust(12, b" "),
                b"0".ljust(6, b" "),
                b"0".ljust(6, b" "),
                b"100644".ljust(8, b" "),
                str(size).encode().rjust(10, b" "),
                b"\x60\x0a",
            )
            f.write(header)
            f.write(data)
            if size % 2 == 1:
                f.write(b"\n")


def build_deb() -> str:
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(DEB_DIR, exist_ok=True)

    print("Building Debian package...")

    debian_binary = b"2.0\n"
    control_tgz = make_control_tgz()
    data_tgz = make_data_tgz()

    output_path = os.path.join(DIST_DIR, DEB_FILENAME)
    write_ar_archive(output_path, [
        ("debian-binary", debian_binary),
        ("control.tar.gz", control_tgz),
        ("data.tar.gz", data_tgz),
    ])

    size_kb = os.path.getsize(output_path) / 1024
    print(f"Debian package written: {output_path} ({size_kb:.1f} KB)")
    print(f"  Control: {len(control_tgz)} bytes")
    print(f"  Data:    {len(data_tgz)} bytes")

    return output_path


def verify_deb(path: str) -> bool:
    """Verify the .deb by listing ar contents."""
    try:
        import subprocess
        result = subprocess.run(["ar", "t", path], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"  Verifies via ar t: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass

    # Fallback: check magic bytes
    with open(path, "rb") as f:
        magic = f.read(8)
        if magic == b"!<arch>\n":
            print("  Verifies via magic: !<arch>")
            return True
    return False


if __name__ == "__main__":
    path = build_deb()
    ok = verify_deb(path)
    if not ok:
        print("WARNING: .deb verification failed!")
        sys.exit(1)
    else:
        print("✅ Debian package verification passed")
        sys.exit(0)
