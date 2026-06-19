# GPUPulse

**Lightweight, real-time GPU and system monitor for Linux.**

Built for people who run heavy local AI workloads (e.g. on NVIDIA GPUs) and want to see what's actually happening with VRAM, temperature, power, and processes — without the monitor itself becoming a resource hog.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

## Features

- **Real-time graphs**: CPU, RAM, NVIDIA GPU (utilization, VRAM, temp, power) + Onboard/iGPU support (AMD real busy %, Intel freq proxy).
- **Processes tab**: Shows Device (NVIDIA 0 / CPU), GPU VRAM usage, detected engines (llama.cpp, Ollama, vLLM, KoboldCPP, etc.). Filter to "GPU processes only" or "CPU only".
- **Fully customizable**: Drag to reorder columns, right-click header to show/hide, state is persisted.
- **Lightweight by design**: 1s polling, visible-only updates for heavy tabs, bounded history buffers.
- **System integration**:
  - System tray + draggable always-on-top Compact view.
  - Kill / Terminate / Renice processes directly.
  - Settings dialog (poll rate, theme, tray behavior, history length).
- **Works everywhere**:
  - Full NVIDIA support (including multi-GPU).
  - Onboard/integrated graphics (Intel/AMD).
  - Pure CPU fallback.
  - Tested on Ubuntu, Linux Mint (XFCE), etc.
- One-command installer that produces a proper `.deb` package.

## Installation (ONE COMMAND)

The easiest and recommended way:

```bash
bash install.sh
```

Or double-click the `Install-GPUPulse.desktop` file (it will run the installer).

This:
- Installs as a real Debian package (managed by apt).
- Adds a desktop menu entry.
- Uses system PySide6 where possible for speed and small size.

**Uninstall cleanly later:**

```bash
sudo apt remove gpupulse
```

See [HOW_TO_RUN.md](HOW_TO_RUN.md) for more options (running from source, manual packaging).

## Quick Start

After installation, launch `gpupulse` from the menu or terminal.

- **Performance** tab: Live line graphs.
- **Processes** tab: Top processes, GPU-aware, with filters and management actions.
- Use the **Settings** button for poll interval, dark theme, etc.
- Right-click the header in the Processes table to customize columns.

## Screenshots

> _Add screenshots here after pushing (Performance graphs + Processes table with Device column)._

Example usage:
- Monitoring Ollama / llama.cpp / vLLM inference.
- Watching GPU + onboard utilization while running local models.

## Why GPUPulse?

- Not another terminal tool like `nvtop`.
- Not a heavy general monitor.
- Focused on what local AI users actually need: VRAM tracking, inference engine identification, low overhead, and support for machines without discrete GPUs.

## Development & Packaging

- `bash install.sh` is the primary one-shot installer (creates `.deb`).
- See `build-deb.sh` and `build.py` (PyInstaller path) for advanced builds.
- Written with PySide6 + pyqtgraph + psutil + optional pynvml.

## Contributing

Contributions welcome! Open an issue or pull request.

Please keep changes lightweight — this app is meant to stay out of the way even when your GPU is at 100%.

## License

GNU General Public License v3.0

This keeps the software free for everyone while preventing anyone from taking the code and selling a closed-source version.

## Name

**GPUPulse** — clear, implies live monitoring.

See [DEVLOG.md](DEVLOG.md) for the full development history.