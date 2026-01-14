# Resize JPG helper by RA-moon

A small macOS utility to batch-resize images to multiple target sizes and set DPI metadata so Photoshop displays it correctly.

© 2026 [RA-moon](https://github.com/RA-moon)


## Download (macOS Apple Silicon)
[Download latest](https://github.com/RA-moon/Image-Resize-Helper/releases/latest/download/Resize%20JPG%20helper%20by%20RA-moon.app.zip)


## Features
- Batch process all images from an input folder
- Up to 5 target presets (Width px / Height px / DPI)
- Creates one output folder per preset (e.g. `2480x736px/`)
- Resize modes: `pad` (default), `crop`, `stretch`
- Outputs JPG and writes DPI metadata (Photoshop-friendly)
- Works as a standalone macOS `.app` (no Python required for end users)

## Requirements (development)
- macOS (Apple Silicon recommended)
- Homebrew `ffmpeg` (only needed if you run from source; in the `.app` build we bundle it)

## Run from source
```bash
cd ~/Desktop/Resize-helper
/opt/homebrew/bin/python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install -U pip
python3 -m pip install pywebview pyinstaller \
  pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-WebKit pyobjc-framework-Quartz pyobjc-framework-Security

python3 images-resize-helper.py
