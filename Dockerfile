FROM ghcr.io/saladtechnologies/comfyui-api:comfy0.3.67-api1.13.3-torch2.8.0-cuda12.8-runtime

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libsamplerate0-dev \
        portaudio19-dev \
        ffmpeg && \
    rm -rf /var/lib/apt/lists/*
