# AI Stack: Ollama + Open-WebUI + ComfyUI

A self-hosted AI inference stack running on a single NVIDIA GPU, orchestrated with Docker Compose. Includes intelligent VRAM management to prevent GPU memory contention between LLM and image generation workloads.

## Services

| Service | Purpose | Port |
|---------|---------|------|
| **Ollama** | LLM inference engine (chat, code, etc.) | [localhost:11434](http://localhost:11434) |
| **Open-WebUI** | Web chat frontend for Ollama | [localhost:3000](http://localhost:3000) |
| **ComfyUI** | Stable Diffusion image/video/audio generation | [localhost:8188](http://localhost:8188) |
| **Grafana** | Metrics visualization | [localhost:3001](http://localhost:3001) |
| **Watchtower** | Automatic Docker image updates (dev only) | — |
| **VRAM Manager** | Automatic GPU memory arbitration | — |

## Hardware

| Component | Specification |
|-----------|--------------|
| GPU | Palit GeForce RTX 5080 (16 GB VRAM) |
| CPU | AMD Ryzen 7 9800X3D |
| RAM | 64 GB DDR5-6000 |
| Storage | 2 TB M.2 SSD PCIe 4.0 |

## Prerequisites

- Docker Engine with GPU support (`nvidia-docker2`)
- NVIDIA Container Toolkit installed
- NVIDIA GPU with sufficient VRAM (16 GB recommended)

## Quick Start

```bash
# Start all services (including VRAM Manager)
docker compose -f docker-compose.dev.yaml up -d

# Check status
docker compose -f docker-compose.dev.yaml ps

# View logs
docker compose -f docker-compose.dev.yaml logs -f

# Monitor VRAM Manager
docker logs -f aistack-vram-manager

# Watch GPU usage
watch -n 1 nvidia-smi
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                Docker Network: ai-stack-network              │
│                                                              │
│  ┌──────────┐   ┌────────────┐   ┌──────────┐              │
│  │  Ollama   │◄──│ Open-WebUI │   │ ComfyUI  │              │
│  │ LLM Host  │   │   Chat UI  │   │ Image Gen│              │
│  │ :11434    │   │  :3000     │   │ :8188    │              │
│  └─────┬─────┘   └────────────┘   └────┬─────┘              │
│        │                                │                    │
│        │         ┌──────────────┐       │                    │
│        └─────────│ VRAM Manager │───────┘                    │
│                  │ GPU Arbiter  │                             │
│                  └──────────────┘                             │
│                                                              │
│  ┌──────────┐   ┌──────────────┐                            │
│  │ Grafana  │   │  Watchtower  │                            │
│  │ Metrics  │   │ Auto-Updates │                            │
│  │ :3001    │   │  (dev only)  │                            │
│  └──────────┘   └──────────────┘                            │
└─────────────────────────────────────────────────────────────┘
                          │
                  ┌───────┴───────┐
                  │  NVIDIA GPU   │
                  │  16 GB VRAM   │
                  └───────────────┘
```

## VRAM Management

The VRAM Manager automatically prevents Ollama from falling back to CPU mode (100x slower) when ComfyUI is using GPU memory. It monitors Ollama's model loading and triggers ComfyUI's `/free` API to release VRAM on demand.

See **[docs/VRAM-Management.md](docs/VRAM-Management.md)** for configuration, tuning, and troubleshooting.

## Configuration

All settings are in [`.env.dev`](.env.dev). Key parameters:

```bash
# VRAM Manager
VRAM_CHECK_INTERVAL=5       # Check every 5 seconds
VRAM_THRESHOLD=75            # Free ComfyUI when VRAM > 75%

# Ollama VRAM limits
OLLAMA_MAX_VRAM=10737418240  # 10 GB
OLLAMA_MAX_LOADED_MODELS=2   # Max models in memory
OLLAMA_NUM_PARALLEL=2        # Parallel requests

# ComfyUI memory mode
COMFYUI_CLI_ARGS=--normalvram
```

## Development Notes

- All content has been written using various AI assistants
- Selection of models, prompting, content supervision, review, testing and refactoring is done by hand
- This is a development configuration — not hardened for production use
