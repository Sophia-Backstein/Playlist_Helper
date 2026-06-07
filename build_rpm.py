#!/usr/bin/env python3
"""Build a valid .rpm package manually with HEADERIMMUTABLE region."""

import struct, os, hashlib, gzip, subprocess, sys, shutil, glob, stat

# The rpm Python module is only available when python3-rpm is installed.
# If missing, we fall back to building via rpmbuild -ba playlist-helper.spec
# which is the standard Fedora build workflow.
try:
    import rpm as _rpm
    HAVE_RPM_MODULE = True
except ImportError:
    HAVE_RPM_MODULE = False

PROJECT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(PROJECT, "dist")
TOPDIR = os.path.join(PROJECT, "rpmbuild")


def shlex_quote(s):
    return "'" + s.replace("'", "'\\''") + "'"


def build_payload():
    build_dir = os.path.join(TOPDIR, "BUILD")
    if not os.path.exists(build_dir):
        print("ERROR: Build directory doesn't exist")
        sys.exit(1)
    payload_raw = os.path.join(TOPDIR, ".payload.raw")
    return build_payload_python()


def build_payload_python():
    build_base = os.path.join(TOPDIR, "BUILD")
    if not os.path.exists(build_base):
        print(f"ERROR: {build_base} not found")
        sys.exit(1)
    def fmt8(val):
        return f"{val:08x}".encode('ascii')
    cpio_data = bytearray()
    entries = []
    # Collect all dirs AND files, including parent directories
    all_dirs = set()
    for root, dirs, fnames in os.walk(build_base):
        rel = os.path.relpath(root, build_base)
        if rel != ".":
            all_dirs.add(rel)
        for dn in sorted(dirs):
            full = os.path.join(root, dn)
            rel2 = os.path.relpath(full, build_base)
            all_dirs.add(rel2)
            # Skip top-level prefix directories (e.g. "opt") — they're NOT in the
            # header's BASENAMES/DIRINDEXES list because collect_files() starts
            # at the next level. Including them causes rpm2archive / rpm.files.archive
            # to fail with "Archive file not in header".
            if '/' not in rel2:
                continue
            entries.append(('dir', full, rel2))
        for fn in sorted(fnames):
            full = os.path.join(root, fn)
            rel2 = os.path.relpath(full, build_base)
            entries.append(('file', full, rel2))
    # Use absolute paths (leading /) in the cpio archive to match
    # the header's DIRNAMES/BASENAMES format. The rpm library expects
    # cpio entry namesizes to match header path lengths.
    entries = [(et, fp, '/' + an) for et, fp, an in entries]
    entries.sort(key=lambda x: (0 if x[0] == 'dir' else 1, x[2]))
    ino = 1
    for etype, fpath, aname in entries:
        name_bytes = aname.encode('utf-8') + b'\x00'
        name_len = len(name_bytes)
        # matching the C library's (rpmcpioReadPad) expectation:
        # magic(6)+hdr(104) puts offset at 110, so name padding = (4 - (110 + name_len) % 4) % 4
        name_pad = (4 - (110 + name_len) % 4) % 4
        if etype == 'dir':
            st = os.lstat(fpath)
            mode = stat.S_IMODE(st.st_mode) | stat.S_IFDIR
            size = 0
        else:
            st = os.lstat(fpath)
            mode = stat.S_IMODE(st.st_mode)
            if stat.S_ISREG(mode):
                mode |= (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) if (st.st_mode & stat.S_IXUSR) else 0
                mode |= stat.S_IFREG
            size = st.st_size
        # newc header: magic(6) + 13 fields of 8 bytes each = 110 bytes
        # Fields: ino, mode, uid, gid, nlink, mtime, filesize, dev_maj, dev_min, rdev_maj, rdev_min, namesize, chksum
        hdr = b"070701"
        hdr += fmt8(ino)   # ino
        hdr += fmt8(mode)  # mode
        hdr += fmt8(st.st_uid) if etype == 'file' else fmt8(0)  # uid
        hdr += fmt8(st.st_gid) if etype == 'file' else fmt8(0)  # gid
        hdr += fmt8(1)   # nlink
        hdr += fmt8(0)   # mtime
        hdr += fmt8(size)  # filesize
        hdr += fmt8(0)   # dev_maj
        hdr += fmt8(0)   # dev_min
        hdr += fmt8(0)   # rdev_maj
        hdr += fmt8(0)   # rdev_min
        hdr += fmt8(name_len)  # namesize
        hdr += fmt8(0)   # chksum
        assert len(hdr) == 110, f"header is {len(hdr)} bytes"
        cpio_data.extend(hdr)
        cpio_data.extend(name_bytes)
        cpio_data.extend(b'\x00' * name_pad)
        if etype != 'dir':
            with open(fpath, 'rb') as f:
                fd = f.read()
            cpio_data.extend(fd)
            alen = (4 - len(fd) % 4) % 4
            cpio_data.extend(b'\x00' * alen)
        ino += 1
    tname = b"TRAILER!!!\x00"
    tnl = len(tname)
    trailer = b"070701" + fmt8(0)+fmt8(0)+fmt8(0)+fmt8(0)+fmt8(1)+fmt8(0)
    trailer += fmt8(0)+fmt8(0)+fmt8(0)+fmt8(0)+fmt8(0)+fmt8(tnl)+fmt8(0)
    trailer = trailer[:110]
    assert len(trailer) == 110, f"trailer is {len(trailer)}"
    cpio_data.extend(trailer); cpio_data.extend(tname)
    tpad = (4 - (110 + tnl) % 4) % 4
    cpio_data.extend(b'\x00' * tpad)
    raw_size = len(cpio_data)
    compressed = gzip.compress(bytes(cpio_data), compresslevel=9)
    print(f"Payload (Python): {raw_size} raw -> {len(compressed)} gzipped bytes")
    return compressed, raw_size


def collect_files(build_base):
    file_entries = []
    for root, dirs, fnames in os.walk(build_base):
        rel = os.path.relpath(root, build_base)
        if rel == ".":
            continue
        for dn in sorted(dirs):
            full = os.path.join(root, dn)
            rel2 = os.path.relpath(full, build_base)
            file_entries.append(('dir', full, "/" + rel2))
        for fn in sorted(fnames):
            full = os.path.join(root, fn)
            rel2 = os.path.relpath(full, build_base)
            file_entries.append(('file', full, "/" + rel2))
    file_entries.sort(key=lambda x: (0 if x[0] == 'dir' else 1, x[2]))
    all_dirs = set()
    for etype, fpath, aname in file_entries:
        parent = os.path.dirname(aname)
        while parent and parent != "/":
            all_dirs.add(parent + "/")
            parent = os.path.dirname(parent)
    dir_list = sorted(all_dirs)
    dir_index_map = {d: i for i, d in enumerate(dir_list)}
    basenames = []; dirindexes = []; filesizes = []; filemodes = []
    filedigests = []; fileflags = []; fileusernames = []; filegroupnames = []
    filedevices = []; fileinodes = []; filelangs = []; filerdews = []
    filemtimes = []; fileverifyflags = []; filelinktos = []
    ino = 1; total_size = 0
    for etype, fpath, aname in file_entries:
        parent = os.path.dirname(aname)
        if parent == "":
            parent = "/"
        parent += "/"
        basename = os.path.basename(aname)
        basenames.append(basename)
        dirindexes.append(dir_index_map[parent])
        if etype == 'dir':
            filesizes.append(0)
            filemodes.append(0o040755)
            filedigests.append('')
            fileflags.append(0)
        else:
            st = os.stat(fpath)
            sz = st.st_size
            filesizes.append(sz)
            mode = 0o100755 if (st.st_mode & 0o100) else 0o100644
            filemodes.append(mode)
            with open(fpath, 'rb') as _f:
                filedigests.append(hashlib.sha256(_f.read()).hexdigest())
            fileflags.append(0)
            total_size += sz
        fileusernames.append('root')
        filegroupnames.append('root')
        filedevices.append(1)
        fileinodes.append(ino); ino += 1
        filelangs.append('')
        filerdews.append(0)
        filemtimes.append(int(os.stat(fpath).st_mtime) if etype != 'dir' else 0)
        fileverifyflags.append(0)
        filelinktos.append('')
    return {
        'basenames': basenames, 'dirnames': dir_list, 'dirindexes': dirindexes,
        'filesizes': filesizes, 'filemodes': filemodes, 'filedigests': filedigests,
        'fileflags': fileflags, 'fileusernames': fileusernames,
        'filegroupnames': filegroupnames, 'filedevices': filedevices,
        'fileinodes': fileinodes, 'filelangs': filelangs, 'filerdews': filerdews,
        'filemtimes': filemtimes, 'fileverifyflags': fileverifyflags,
        'filelinktos': filelinktos, 'total_size': total_size,
    }

def build_main_header(payload_data, payload_hash=None, raw_size=0):
    if not HAVE_RPM_MODULE:
        print("ERROR: python3-rpm module not available. Falling back to rpmbuild -ba .spec")
        print("Run: rpmbuild -ba playlist-helper.spec")
        sys.exit(1)
    h = _rpm.hdr()
    h[_rpm.RPMTAG_NAME] = 'playlist-helper'
    h[_rpm.RPMTAG_VERSION] = '1.0.0'
    h[_rpm.RPMTAG_RELEASE] = '1.fc43'
    h[_rpm.RPMTAG_SUMMARY] = 'Audio file management application'
    h[_rpm.RPMTAG_DESCRIPTION] = 'Desktop app for managing audio files.'
    h[_rpm.RPMTAG_LICENSE] = 'MIT'
    h[_rpm.RPMTAG_GROUP] = 'Applications/Multimedia'
    h[_rpm.RPMTAG_ARCH] = 'noarch'
    h[_rpm.RPMTAG_OS] = 'linux'
    h[_rpm.RPMTAG_PLATFORM] = 'noarch-linux'
    h[_rpm.RPMTAG_PAYLOADFORMAT] = 'cpio'
    h[_rpm.RPMTAG_PAYLOADCOMPRESSOR] = 'gzip'
    h[_rpm.RPMTAG_PAYLOADFLAGS] = '9'
    h[_rpm.RPMTAG_VENDOR] = 'Playlist Helper'
    h[_rpm.RPMTAG_URL] = 'https://example.com/playlist-helper'
    h[_rpm.RPMTAG_DISTRIBUTION] = 'Fedora'
    h[_rpm.RPMTAG_REQUIRENAME] = ['python3', 'python3-pyside6', 'ffmpeg-free']
    h[_rpm.RPMTAG_REQUIREVERSION] = ['3.10', '6.6.0', '']
    h[_rpm.RPMTAG_REQUIREFLAGS] = [0x0c, 0x0c, 0x00]
    
    if payload_hash is not None:
        try: h[_rpm.RPMTAG_PAYLOADSHA256] = [payload_hash]
        except: pass
        try: h[_rpm.RPMTAG_PAYLOADSHA256ALT] = [payload_hash]
        except: pass
        try: h[_rpm.RPMTAG_PAYLOADSIZE] = raw_size
        except: pass
    
    # Add file metadata from the BUILD directory
    build_base = os.path.join(TOPDIR, "BUILD")
    fm = collect_files(build_base)
    h[_rpm.RPMTAG_SIZE] = fm['total_size']
    h[_rpm.RPMTAG_BASENAMES] = fm['basenames']
    h[_rpm.RPMTAG_DIRNAMES] = fm['dirnames']
    h[_rpm.RPMTAG_DIRINDEXES] = fm['dirindexes']
    h[_rpm.RPMTAG_FILESIZES] = fm['filesizes']
    h[_rpm.RPMTAG_FILEMODES] = fm['filemodes']
    h[_rpm.RPMTAG_FILEDIGESTS] = fm['filedigests']
    h[_rpm.RPMTAG_FILEFLAGS] = fm['fileflags']
    h[_rpm.RPMTAG_FILEUSERNAME] = fm['fileusernames']
    h[_rpm.RPMTAG_FILEGROUPNAME] = fm['filegroupnames']
    h[_rpm.RPMTAG_FILEDEVICES] = fm['filedevices']
    h[_rpm.RPMTAG_FILEINODES] = fm['fileinodes']
    h[_rpm.RPMTAG_FILELANGS] = fm['filelangs']
    h[_rpm.RPMTAG_FILERDEVS] = fm['filerdews']
    h[_rpm.RPMTAG_FILEMTIMES] = fm['filemtimes']
    h[_rpm.RPMTAG_FILEVERIFYFLAGS] = fm['fileverifyflags']
    h[_rpm.RPMTAG_FILELINKTOS] = fm['filelinktos']
    try: h[_rpm.RPMTAG_FILEDIGESTALGO] = 8
    except: pass
    # Post-install script creates desktop entry, launcher symlink, and icon
    postin = """ln -sf /opt/playlist-helper/playlist-helper /usr/bin/playlist-helper
cp /opt/playlist-helper/playlist-helper.desktop /usr/share/applications/
cp /opt/playlist-helper/icon.png /usr/share/pixmaps/playlist-helper.png
"""
    try: h[_rpm.RPMTAG_POSTIN] = postin
    except: pass
    try: h[_rpm.RPMTAG_POSTINPROG] = ['/bin/sh']
    except: pass
    try: h[_rpm.RPMTAG_POSTINFLAGS] = [0]
    except: pass
    tmp_path = os.path.join(TOPDIR, '.main_hdr.tmp')
    fd = _rpm.fd(tmp_path, 'w', 'rpm')
    h.write(fd)
    fd.close()
    with open(tmp_path, 'rb') as f:
        blob = f.read()
    os.unlink(tmp_path)
    raw_magic, raw_ver, ne, hsize = struct.unpack(">IIII", blob[:16])
    print(f"Main raw: magic=0x{raw_magic:08X}, ne={ne}, hs={hsize}")
    idx = blob[16:16+ne*16]
    store = blob[16+ne*16:16+ne*16+hsize]
    new_ne = ne + 1
    new_hsize = hsize + 16
    ril_offset = -(new_ne * 16)
    region_data = struct.pack(">IIii", 63, 7, ril_offset, 16)
    new_idx = struct.pack(">IIII", 63, 7, new_hsize - 16, 16)
    new_idx += idx
    new_store = store + region_data
    new_blob = struct.pack(">IIII", 0x8EADE801, 0, new_ne, new_hsize)
    new_blob += new_idx
    new_blob += new_store
    pad = (8 - len(new_blob) % 8) % 8
    new_blob += b'\x00' * pad
    print(f"Main header: ne={new_ne}, hs={new_hsize}, total={len(new_blob)} bytes")
    return new_blob


def build_sig_header(main_header_blob):
    main_hash = hashlib.sha256(main_header_blob).hexdigest()
    sha256_hex = main_hash.encode('ascii') + b'\x00'
    ril_offset = -(2 * 16)
    region_data = struct.pack(">IIii", 62, 7, ril_offset, 16)
    store = sha256_hex + region_data
    hsize = len(store)
    entries = struct.pack(">IIIIIIII",
        62, 7, hsize - 16, 16,
        273, 6, 0, 1)
    ne = 2
    header = struct.pack(">IIII", 0x8EADE801, 0, ne, hsize)
    header += entries + store
    pad = (8 - len(header) % 8) % 8
    header += b'\x00' * pad
    print(f"Sig header: {len(header)} bytes")
    return header


def build_lead():
    lead = struct.pack(">4sBBhh",
        b'\xed\xab\xee\xdb', 3, 0, 5, 0)
    lead += b'\x01\x00' + b'\x00' * 64
    lead += b'\x00' * 2 + b'\x00' * 2 + b'\x00' * 16
    assert len(lead) == 96, f"Lead is {len(lead)} bytes"
    return lead


def build_rpm():
    # Fall back to rpmbuild -ba .spec when python3-rpm module is unavailable
    if not HAVE_RPM_MODULE:
        print("python3-rpm module not found — falling back to rpmbuild -ba playlist-helper.spec")
        spec_path = os.path.join(PROJECT, "playlist-helper.spec")
        if not os.path.exists(spec_path):
            print(f"ERROR: {spec_path} not found")
            sys.exit(1)
        subprocess.run(
            [sys.executable, "setup.py", "sdist", "--format=gztar"],
            cwd=PROJECT, capture_output=True, timeout=120,
        )
        rpmbuild_sources = os.path.expanduser("~/rpmbuild/SOURCES")
        os.makedirs(rpmbuild_sources, exist_ok=True)
        for tgz in glob.glob(os.path.join(DIST, "playlist-helper-*.tar.gz")):
            shutil.copy2(tgz, rpmbuild_sources)
        result = subprocess.run(
            ["rpmbuild", "-ba", spec_path],
            cwd=PROJECT, timeout=300,
        )
        if result.returncode != 0:
            print("ERROR: rpmbuild failed")
            sys.exit(1)
        print("RPM built via rpmbuild -ba. Check ~/rpmbuild/RPMS/ for the .rpm file")
        return

    os.makedirs(DIST, exist_ok=True)
    os.makedirs(TOPDIR, exist_ok=True)
    stage_build_tree()
    payload_data, raw_size = build_payload()

    # First pass: build pieces without payload hash to determine sizes
    main_hdr = build_main_header(payload_data, raw_size=raw_size)
    sig_hdr = build_sig_header(main_hdr)
    lead = build_lead()

    # Compute trailing 8-byte padding for the final file
    rpm_sans_pad = lead + sig_hdr + main_hdr + payload_data
    pad = (8 - len(rpm_sans_pad) % 8) % 8

    # Compute payload hash INCLUDING the padding (what rpm verifies against)
    payload_in_file = payload_data + b'\x00' * pad
    correct_payload_hash = hashlib.sha256(payload_in_file).hexdigest()

    # Second pass: rebuild main header with correct payload hash
    main_hdr = build_main_header(payload_data, payload_hash=correct_payload_hash, raw_size=raw_size)
    # Rebuild sig header too (main header blob changed)
    sig_hdr = build_sig_header(main_hdr)

    # Final assembly
    rpm_path = os.path.join(DIST, "playlist-helper-1.0.0-1.fc43.noarch.rpm")
    rpm_data = lead + sig_hdr + main_hdr + payload_data
    pad = (8 - len(rpm_data) % 8) % 8
    rpm_data += b'\x00' * pad
    with open(rpm_path, 'wb') as f:
        f.write(rpm_data)
    size_kb = len(rpm_data) / 1024
    print(f"\nRPM written: {rpm_path} ({size_kb:.1f} KB)")
    verify_rpm(rpm_path)


def stage_build_tree():
    build_root = os.path.join(TOPDIR, "BUILD")
    app_dir = os.path.join(build_root, "opt", "playlist-helper")
    if os.path.exists(app_dir):
        return
    os.makedirs(app_dir, exist_ok=True)
    for d in ['BUILDROOT', 'RPMS/noarch', 'SOURCES', 'SPECS', 'SRPMS']:
        os.makedirs(os.path.join(TOPDIR, d), exist_ok=True)
    src_main = os.path.join(PROJECT, "main.py")
    if os.path.exists(src_main):
        shutil.copy2(src_main, os.path.join(app_dir, "main.py"))
    src_dir = os.path.join(PROJECT, "src")
    src_dest = os.path.join(app_dir, "src")
    if os.path.exists(src_dir):
        if os.path.exists(src_dest):
            shutil.rmtree(src_dest)
        shutil.copytree(src_dir, src_dest)

    # Launcher script
    launcher = os.path.join(app_dir, "playlist-helper.sh")
    with open(launcher, 'w') as f:
        f.write("#!/bin/bash\ncd /opt/playlist-helper && exec python3 main.py\n")
    os.chmod(launcher, 0o755)

    # /usr/bin symlink target (placed inside /opt so RPM owns it, postinst creates symlink)
    bin_target = os.path.join(app_dir, "playlist-helper")
    with open(bin_target, 'w') as f:
        f.write("#!/bin/bash\nexec /usr/bin/python3 /opt/playlist-helper/main.py\n")
    os.chmod(bin_target, 0o755)

    # Desktop entry (placed in /opt, postinst copies it to /usr/share/applications)
    desk_path = os.path.join(app_dir, "playlist-helper.desktop")
    with open(desk_path, 'w') as f:
        f.write("""[Desktop Entry]
Type=Application
Name=Playlist Helper
Comment=Audio file management and processing application
Exec=/usr/bin/playlist-helper
Icon=playlist-helper
Terminal=false
Categories=Audio;AudioVideo;Utility;
StartupNotify=true
""")

    # Icon (placed in /opt, postinst copies it to /usr/share/pixmaps)
    icon_src = os.path.join(PROJECT, "resources", "icon.png")
    if os.path.exists(icon_src):
        shutil.copy2(icon_src, os.path.join(app_dir, "icon.png"))

    print(f"Staged files to {build_root}")


def verify_rpm(rpm_path):
    res = subprocess.run(["rpm", "-qpi", rpm_path], capture_output=True, text=True, timeout=15)
    if res.returncode == 0:
        print("✅ rpm -qpi SUCCEEDS!")
        print(res.stdout[:2000])
    else:
        print(f"❌ rpm -qpi FAILED (code {res.returncode})")
        print(f"STDERR: {res.stderr[:500]}")
        print(f"STDOUT: {res.stdout[:500]}")
        debug_rpm(rpm_path)


def debug_rpm(path):
    with open(path, 'rb') as f:
        data = f.read()
    print(f"\nFile size: {len(data)} bytes")
    off = 96
    magic, ver, ne, hs = struct.unpack(">IIII", data[off:off+16])
    print(f"Sig header: magic=0x{magic:08X}, ne={ne}, hs={hs}")
    idx_end = off + 16 + ne * 16
    store_end = idx_end + hs
    pad_end = (store_end + 7) & ~7
    for i in range(ne):
        eo = off + 16 + i * 16
        tag, typ, eoff, cnt = struct.unpack(">IIII", data[eo:eo+16])
        print(f"  sig[{i}] tag={tag} type={typ} off={eoff} cnt={cnt}")
    off2 = pad_end
    magic2, ver2, ne2, hs2 = struct.unpack(">IIII", data[off2:off2+16])
    print(f"Main header: magic=0x{magic2:08X}, ne={ne2}, hs={hs2}")
    idx_end2 = off2 + 16 + ne2 * 16
    for i in range(min(ne2, 20)):
        eo = off2 + 16 + i * 16
        tag, typ, eoff, cnt = struct.unpack(">IIII", data[eo:eo+16])
        print(f"  main[{i}] tag={tag} type={typ} off={eoff} cnt={cnt}")


if __name__ == '__main__':
    build_rpm()
