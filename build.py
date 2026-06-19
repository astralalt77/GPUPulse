#!/usr/bin/env python3
"""
Simple build script for GPUPulse using PyInstaller.

Usage:
    python build.py

This produces a standalone executable in dist/GPUPulse

For AppImage (recommended for Linux distro compatibility):
  1. Run this to get the binary in dist/
  2. Use appimagetool or linuxdeploy to package.

Requirements for build:
    pip install pyinstaller
"""

import PyInstaller.__main__
import sys
import os

def main():
    print("Building GPUPulse standalone...")

    args = [
        'main.py',
        '--name=GPUPulse',
        '--onefile',
        '--windowed',  # no console on Linux/Windows
        '--add-data=README.md:.',
        '--add-data=LICENSE:.',
        '--hidden-import=PySide6',
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui',
        '--hidden-import=PySide6.QtWidgets',
        '--collect-all=PySide6',
        '--exclude-module=pyqtgraph.opengl',  # optional, causes issues on some systems without PyOpenGL
        '--exclude-module=PySide6.scripts',  # avoid internal deploy stuff
        # Include any other data if needed
        '--clean',
        '--noconfirm',
    ]

    # For Linux AppImage friendly, onefolder sometimes better, but onefile is fine too.
    PyInstaller.__main__.run(args)
    print("\nBuild complete. Check dist/GPUPulse")
    print("To make an AppImage:")
    print("  - Use https://github.com/AppImage/AppImageKit or linuxdeployqt like tools")
    print("  - Or: appimagetool-x86_64.AppImage --appimage-extract-and-run AppDir")


if __name__ == "__main__":
    main()
