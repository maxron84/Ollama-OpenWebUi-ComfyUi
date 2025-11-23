#!/usr/bin/env bash
#
# Copy this script into the currently running ComfyUI Docker Container and execute it there
#
set -euo pipefail

# Update package lists and upgrade local packages
apt-get update && apt-get upgrade

# Install required packages without extra recommendations
apt-get install -y --no-install-recommends \
    build-essential \
    libsamplerate0-dev \
    portaudio19-dev \
    ffmpeg
