#!/usr/bin/env bash
# Playlist Helper — Linux Installer
# Works on Fedora/RHEL and Debian/Ubuntu.
# Usage: sudo bash install_linux.sh [--skip-tests]
set -euo pipefail

APP_NAME="Playlist Helper"
APP_DIR="/opt/playlist-helper"
BIN_LINK="/usr/local/bin/playlist-helper"
DESKTOP_FILE="/usr/share/applications/playlist-helper.desktop"
ICON_DIR="/usr/share/icons/hicolor/256x256/apps"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Root check
if [[ $EUID -ne 0 ]]; then
    error "This installer must be run as root (sudo)."
    exit 1
fi

# ---- Distro detection ----
detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS_ID="$ID"
        OS_ID_LIKE="$ID_LIKE"
    elif [[ -f /etc/fedora-release ]]; then
        OS_ID="fedora"
    elif [[ -f /etc/debian_version ]]; then
        OS_ID="debian"
    else
        OS_ID="unknown"
    fi
}

detect_distro
info "Detected distribution: ${OS_ID}${OS_ID_LIKE:+ (${OS_ID_LIKE})}"

is_fedora() {
    [[ "$OS_ID" == "fedora" || "$OS_ID_LIKE" == *"fedora"* ]]
}

is_debian() {
    [[ "$OS_ID" == "debian" || "$OS_ID" == "ubuntu" || "$OS_ID_LIKE" == *"debian"* ]]
}

# ---- Dependency installation ----
info "Installing system dependencies..."

if is_fedora; then
    dnf install -y \
        python3 \
        python3-pip \
        python3-devel \
        ffmpeg \
        file \
        --setopt=install_weak_deps=False 2>/dev/null || \
    dnf install -y python3 ffmpeg file

elif is_debian; then
    apt-get update -qq
    apt-get install -y -qq \
        python3 \
        python3-pip \
        python3-venv \
        ffmpeg \
        file
else
    warn "Unknown distribution. Attempting pip install only."
    warn "Make sure ffmpeg and python3 are installed manually."
fi

# Install Python dependencies
info "Installing Python dependencies..."
pip3 install --quiet --upgrade pip
pip3 install --quiet -r "$SCRIPT_DIR/requirements.txt" || \
    pip3 install --quiet PySide6

# ---- Application installation ----
info "Installing ${APP_NAME} to ${APP_DIR}..."
mkdir -p "$APP_DIR"
mkdir -p "$ICON_DIR"

# Copy source tree (exclude build/dist/tests)
rsync -a --delete \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='.wine' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='build/' \
    --exclude='dist/' \
    --exclude='rpmbuild/' \
    --exclude='deb_build/' \
    --exclude='deb_dist/' \
    --exclude='*.egg-info' \
    "$SCRIPT_DIR/src/" "$APP_DIR/src/" 2>/dev/null || \
    cp -r "$SCRIPT_DIR/src" "$APP_DIR/"

# Copy main entry point
cp "$SCRIPT_DIR/main.py" "$APP_DIR/main.py"
chmod 644 "$APP_DIR/main.py"

# Copy requirements
cp "$SCRIPT_DIR/requirements.txt" "$APP_DIR/requirements.txt"

# Copy resources
if [[ -d "$SCRIPT_DIR/resources" ]]; then
    mkdir -p "$APP_DIR/resources"
    rsync -a --delete "$SCRIPT_DIR/resources/" "$APP_DIR/resources/" 2>/dev/null || \
        cp -r "$SCRIPT_DIR/resources" "$APP_DIR/"
fi

# Copy test files (one per format for post-install verification)
# test_all.py reads from tests/original/, so samples go there
mkdir -p "$APP_DIR/tests/original"
if [[ -d "$SCRIPT_DIR/resources/test_samples" ]]; then
    cp "$SCRIPT_DIR/resources/test_samples/"* "$APP_DIR/tests/original/" 2>/dev/null || true
fi
cp "$SCRIPT_DIR/tests/test_all.py" "$APP_DIR/tests/test_all.py"
cp "$SCRIPT_DIR/tests/cover_test.png" "$APP_DIR/tests/cover_test.png" 2>/dev/null || true

# ---- Launcher script ----
info "Creating launcher..."
cat > "$APP_DIR/playlist-helper.sh" <<'LAUNCHER'
#!/usr/bin/env bash
cd /opt/playlist-helper && exec python3 main.py "$@"
LAUNCHER
chmod 755 "$APP_DIR/playlist-helper.sh"

# Symlink into PATH
ln -sf "$APP_DIR/playlist-helper.sh" "$BIN_LINK"

# ---- Desktop entry ----
info "Creating desktop entry..."
cat > "$DESKTOP_FILE" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Playlist Helper
Comment=Audio file management and processing application
Exec=/usr/local/bin/playlist-helper
Icon=playlist-helper
Terminal=false
Categories=Audio;AudioVideo;Utility;
StartupNotify=true
DESKTOP

# Icon
if [[ -f "$SCRIPT_DIR/resources/icon.png" ]]; then
    cp "$SCRIPT_DIR/resources/icon.png" "$ICON_DIR/playlist-helper.png"
fi

# ---- Post-install verification ----
info "Verifying installation..."
if command -v ffmpeg &>/dev/null; then
    info "  ffmpeg: $(ffmpeg -version 2>&1 | head -1)"
else
    warn "  ffmpeg: NOT FOUND — volume analysis will fail."
fi
if python3 -c "import PySide6" 2>/dev/null; then
    info "  PySide6: $(python3 -c "import PySide6; print(PySide6.__version__)")"
else
    error "  PySide6: NOT FOUND — GUI will not start."
fi

# ---- Run tests on sample files ----
SKIP_TESTS=false
for arg in "$@"; do
    [[ "$arg" == "--skip-tests" ]] && SKIP_TESTS=true
done

if [[ "$SKIP_TESTS" == "false" ]]; then
    if [[ -f "$APP_DIR/tests/test_all.py" && -d "$APP_DIR/tests/original" ]]; then
        info "Running post-install tests on sample files (one per format)..."
        pushd "$APP_DIR" >/dev/null
        python3 tests/test_all.py --limit-per-format 1 2>&1 || \
        warn "Test run exited with non-zero (may be format-specific). See above."
        popd >/dev/null
    else
        warn "Test samples not found — skipping post-install tests."
        warn "  Expected: $APP_DIR/tests/original/*"
    fi
else
    info "Post-install tests skipped (--skip-tests)."
fi

info "Installation complete!"
info ""
info "Run:  playlist-helper"
info "Or:   /usr/local/bin/playlist-helper"
info ""
info "To uninstall, remove these files:"
info "  sudo rm -rf $APP_DIR $BIN_LINK $DESKTOP_FILE $ICON_DIR/playlist-helper.png"
