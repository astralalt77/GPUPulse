#!/bin/bash
#
# GPUPulse - One-shot installer (fast, no PyInstaller bundling)
#
# THE ONLY COMMAND:
#   bash install.sh
#
# This installs GPUPulse as a proper .deb using system PySide6.
# Fast install (seconds, not minutes).
# Managed by apt for easy uninstall.
#
# After: gpupulse in menu and command.
# Uninstall: sudo apt remove gpupulse

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  GPUPulse One-Command Installer (fast)"
echo "========================================"
echo
echo "Installing as system package (managed by apt)..."

if ! command -v apt-get &> /dev/null; then
    echo "ERROR: Debian/Ubuntu-based only."
    exit 1
fi

VERSION="0.3.0"
ARCH="amd64"
DEB_BUILD_DIR=$(mktemp -d /tmp/gpupulse-pkg-XXXXXX)
PACKAGE_DIR="$DEB_BUILD_DIR/gpupulse_${VERSION}_${ARCH}"

echo "[1/3] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv dpkg-dev libxcb-cursor0 libxkbcommon-x11-0 || true  # some Qt libs; || true so it doesn't fail if not available


echo "[2/3] Installing Python packages via pip (PySide6 etc.)..."
pip install --quiet --break-system-packages PySide6 pyqtgraph nvidia-ml-py psutil || echo "Note: if pip complains about externally-managed, it may have worked or you can run the pip command manually with --break-system-packages after."

echo "[3/3] Building and installing .deb..."

mkdir -p "$PACKAGE_DIR/DEBIAN"
mkdir -p "$PACKAGE_DIR/usr/bin"
mkdir -p "$PACKAGE_DIR/usr/share/gpupulse"
mkdir -p "$PACKAGE_DIR/usr/share/applications"

cp main.py "$PACKAGE_DIR/usr/share/gpupulse/"
cp -r gpupulse "$PACKAGE_DIR/usr/share/gpupulse/"

cat > "$PACKAGE_DIR/usr/bin/gpupulse" << 'LAUNCH'
#!/bin/sh
cd /usr/share/gpupulse
exec python3 main.py "$@"
LAUNCH
chmod +x "$PACKAGE_DIR/usr/bin/gpupulse"

cat > "$PACKAGE_DIR/usr/share/applications/gpupulse.desktop" << 'DESK'
[Desktop Entry]
Version=1.0
Type=Application
Name=GPUPulse
Comment=Lightweight real-time GPU and system monitor for Linux
Exec=/usr/bin/gpupulse
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;Utility;
Keywords=GPU;monitor;system;task;AI;inference;
StartupNotify=true
DESK

cat > "$PACKAGE_DIR/DEBIAN/control" << 'CTRL'
Package: gpupulse
Version: 0.3.0
Section: utils
Priority: optional
Architecture: amd64
Maintainer: GPUPulse Developers
Depends: python3
Description: Lightweight real-time GPU and system monitor for Linux
 GPUPulse is a lightweight GUI for monitoring CPU, RAM and especially GPU
 (VRAM, temp, utilization, processes) for local AI inference workloads.
 It is designed to be very lightweight and integrates with the system package manager.
CTRL

mkdir -p dist
dpkg-deb --build --root-owner-group "$PACKAGE_DIR" dist/gpupulse_${VERSION}_${ARCH}.deb >/dev/null

DEB_FILE="dist/gpupulse_${VERSION}_${ARCH}.deb"

sudo dpkg -i "$DEB_FILE" || true
sudo apt-get install -f -y -qq

rm -rf "$DEB_BUILD_DIR"

echo
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo
echo "GPUPulse is installed and managed by apt."
echo "Launch from menu or type: gpupulse"
echo
echo "Uninstall: sudo apt remove gpupulse"
echo
hash -r 2>/dev/null || true
