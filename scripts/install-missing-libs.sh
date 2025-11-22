#!/usr/bin/env bash
set -euo pipefail

# Update package lists and upgrade local packages
apt-get update && apt-get upgrade

# Install required packages without extra recommendations
apt-get install -y --no-install-recommends \
    build-essential \
    libsamplerate0-dev \
    portaudio19-dev \
    ffmpeg
