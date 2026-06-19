# How to run GPUPulse safely on your machines

## ONE COMMAND (or double-click)

```bash
bash install.sh
```

Or double-click the `Install-GPUPulse.desktop` file.

One command only. The app is installed as a proper .deb (managed by apt, appears in menu).

Uninstall later with:
```bash
sudo apt remove gpupulse
```

## On NVIDIA systems (Ubuntu, Mint, etc.)

Use the same commands above. The app will automatically detect NVIDIA (or fallback to onboard/CPU) and show GPU utilization, VRAM, temperature, power graphs, and per-process GPU memory where available.

## Making it even lighter during heavy AI work

- Default poll = 1 second (good balance)
- You can raise it to 2–5 seconds in the UI spinner at the top
- Process table only updates when you have that tab open (2s rate)
- Graphs use fixed-size deques — memory usage is bounded

The monitor is deliberately designed to use very little CPU/GPU itself.

## Packaging / Development notes

The `install.sh` script already produces and installs a proper .deb for you (recommended for normal use).

For manual rebuild:

```bash
bash install.sh
```

See `build-deb.sh` (and the old `build.py` PyInstaller path) if you want to customize the package.

Uninstall always works with:

```bash
sudo apt remove gpupulse
```

GPUPulse is now feature complete for the main goals:
- Real-time graphs for CPU, RAM, NVIDIA + onboard GPU
- Processes with Device column (shows NVIDIA vs CPU) + GPU/CPU filter
- Full column customization, tray + compact view, settings, kill/renice
- One-command .deb install that works on Mint/Ubuntu (and similar)

Ready to push to GitHub!