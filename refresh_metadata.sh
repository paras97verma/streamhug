#!/bin/bash

# Navigate to the project root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "Clearing metadata and cache directories..."
# Clean all subdirectories in media/cache, leaving .gitkeep alone
rm -rf media/cache/*
# Re-add .gitkeep if it got deleted (rm -rf * usually ignores dotfiles, but just in case)
touch media/cache/.gitkeep

echo "Triggering file watcher to rescan the library..."
# Touch all video files in media/originals to update their modification times.
# The backend watcher (watcher.py) listens to on_modified events and will trigger a full scan and HLS pre-transcoding.
find media/originals -type f -exec touch {} +

echo "Done! The StreamHug backend will now begin rescanning the library in the background."
