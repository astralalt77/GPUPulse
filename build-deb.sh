#!/bin/bash
#
# GPUPulse Debian package builder
#
# This script:
# 1. Builds a standalone binary using PyInstaller (if needed)
# 2. Creates a proper .deb package
# 3. The resulting .deb can be installed with dpkg or apt
# 4. Uninstall with: sudo apt remove gpupulse   or   sudo dpkg -r gpupulse
#
# Usage:
#   ./build-deb.sh
#
# Requirements:
#   - python3
#   - pip install pyinstaller
#   - dpkg-deb (usually comes with dpkg)
#
# Output: dist/gpupulse_VERSION_amd64.deb

set -e

APP_NAME="gpupulse"
VERSION="0.2.0"
ARCH="amd64"
MAINTAINER="Your Name <you@example.com>"
DESCRIPTION="Lightweight real-time GPU and system monitor for Linux"
DEPENDS="libc6"   # Minimal since it's a static-ish binary from PyInstaller

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/deb-build"
PACKAGE_DIR="$BUILD_DIR/${APP_NAME}_${VERSION}_${ARCH}"

echo "=== GPUPulse .deb Builder ==="
echo "Version: $VERSION"
echo

# Step 1: Ensure we have a standalone binary
echo "[1/4] Building standalone binary with PyInstaller..."
if [ ! -f "$DIST_DIR/GPUPulse" ] && [ ! -f "$DIST_DIR/gpupulse" ]; then
    echo "Creating temporary build environment (to avoid system Python issues)..."
    BUILD_VENV=$(mktemp -d /tmp/gpupulse-build-XXXXXX)
    python3 -m venv "$BUILD_VENV"
    source "$BUILD_VENV/bin/activate"
    pip install --upgrade pip pyinstaller
    python "$SCRIPT_DIR/build.py"
    deactivate
    rm -rf "$BUILD_VENV"
fi

# Find the binary (PyInstaller uses GPUPulse or gpupulse)
BINARY=""
if [ -f "$DIST_DIR/GPUPulse" ]; then
    BINARY="$DIST_DIR/GPUPulse"
elif [ -f "$DIST_DIR/gpupulse" ]; then
    BINARY="$DIST_DIR/gpupulse"
else
    echo "ERROR: No binary found in dist/. Run ./build.py first."
    exit 1
fi

echo "Found binary: $BINARY"

# Step 2: Prepare package structure
echo "[2/4] Preparing package structure..."
rm -rf "$BUILD_DIR"
mkdir -p "$PACKAGE_DIR/DEBIAN"
mkdir -p "$PACKAGE_DIR/usr/bin"
mkdir -p "$PACKAGE_DIR/usr/share/applications"

# Copy binary
cp "$BINARY" "$PACKAGE_DIR/usr/bin/gpupulse"
chmod +x "$PACKAGE_DIR/usr/bin/gpupulse"

# Copy desktop file
if [ -f "$SCRIPT_DIR/gpupulse.desktop" ]; then
    cp "$SCRIPT_DIR/gpupulse.desktop" "$PACKAGE_DIR/usr/share/applications/"
else
    cat > "$PACKAGE_DIR/usr/share/applications/gpupulse.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=GPUPulse
Comment=Lightweight GPU and system monitor for Linux
Exec=/usr/bin/gpupulse
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;Utility;
Keywords=GPU;monitor;system;task;AI;inference;
StartupNotify=true
EOF
fi

# Step 3: Create control file
echo "[3/4] Creating DEBIAN/control file..."
cat > "$PACKAGE_DIR/DEBIAN/control" << EOF
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: $MAINTAINER
Depends: $DEPENDS
Description: $DESCRIPTION
 GPUPulse is a lightweight, real-time GPU and system monitor designed
 for Linux users running local AI workloads. It provides Windows
 Task Manager-style monitoring with a focus on GPU metrics (VRAM,
 temperature, utilization) while remaining very lightweight.
 .
 Features:
  * Real-time line graphs for CPU, RAM, and GPU
  * Per-process GPU memory usage
  * Detection for common inference engines (llama.cpp, Ollama, vLLM, etc.)
  * Process management (terminate, kill, renice)
  * System tray and compact view
  * Fully managed by apt/dpkg
EOF

# Step 4: Build the .deb
echo "[4/4] Building .deb package..."
mkdir -p "$DIST_DIR"
dpkg-deb --build --root-owner-group "$PACKAGE_DIR" "$DIST_DIR"

DEB_FILE=$(ls "$DIST_DIR"/gpupulse_*_${ARCH}.deb 2>/dev/null | head -1)
if [ -n "$DEB_FILE" ]; then
    echo
    echo "========================================"
    echo "SUCCESS!"
    echo "Package created: $DEB_FILE"
    echo
    echo "To install:"
    echo "  sudo dpkg -i $DEB_FILE"
    echo "  # or"
    echo "  sudo apt install $DEB_FILE"
    echo
    echo "To uninstall later:"
    echo "  sudo apt remove gpupulse"
    echo "  # or"
    echo "  sudo dpkg -r gpupulse"
    echo "========================================"
else
    echo "ERROR: Failed to build .deb"
    exit 1
fi

# Cleanup build dir
rm -rf "$BUILD_DIR"

echo
echo "You can also copy the .deb to your other machines and install there."
