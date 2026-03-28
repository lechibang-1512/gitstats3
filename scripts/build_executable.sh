#!/bin/bash
set -e

# Activate venv
source .venv/bin/activate

# Clean previous builds
rm -rf build dist

# Run PyInstaller
# --onefile: Create a single executable
# --add-data: Include assets and source files
# --name: Name of the output binary
pyinstaller --onefile \
    --name gitstats3 \
    --add-data "src/assets:src/assets" \
    --add-data "src/gitstats_strings.json:src" \
    --collect-all fastapi \
    --collect-all uvicorn \
    gitstats.py

echo "Build complete! Executable is at dist/gitstats3"
