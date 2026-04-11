# VRAM Management

## Overview

The VRAM Manager is a Python service that runs as a Docker container alongside Ollama and ComfyUI. It monitors Ollama's model loading and automatically frees ComfyUI's VRAM when needed, preventing Ollama from falling back to CPU mode (which is ~100x slower).

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│         VRAM Manager (Docker Container)                  │
│         Monitors every 5 seconds (configurable)          │
└─────────────────────────────────────────────────────────┘
            │                            │
            ▼                            ▼
    ┌──────────────┐            ┌──────────────┐
    │    Ollama    │            │   ComfyUI    │
    │  GET /api/ps │            │  GET /stats  │
    └──────────────┘            └──────────────┘
            │                            │
            ▼                            │
    New model loading?                   │
            │                            │
            ├─── YES ────────────────────┤
            │                            ▼
            │                   POST /free API
            │                   (cache + models)
            │                            │
            ▼                            ▼
    Ollama loads model using freed VRAM
```

### Triggers

1. **New Model Loading** — A new model name appears in Ollama's `/api/ps` response
2. **VRAM Threshold** — Total GPU memory usage exceeds 75% (configurable)
3. **Rate Limited** — Minimum 30 seconds between frees to prevent thrashing

### Two-Stage Freeing

1. **Soft Free** (default) — Clears ComfyUI's memory cache only (`unload_models=false`)
2. **Aggressive Free** — If VRAM remains above 85% after soft free, fully unloads models (`unload_models=true`)

---

## Configuration

All settings are in `.env.dev`:

```bash
# VRAM Manager
VRAM_MANAGER_CONTAINER_NAME=aistack-vram-manager
VRAM_CHECK_INTERVAL=5           # Check interval in seconds
VRAM_THRESHOLD=75               # Free ComfyUI when VRAM exceeds this %
VRAM_DEBUG=false                # Enable debug logging

# Ollama VRAM limits
OLLAMA_MAX_VRAM=10737418240     # 10 GB max VRAM allocation
OLLAMA_MAX_LOADED_MODELS=2      # Keep max 2 models in memory
OLLAMA_NUM_PARALLEL=2           # Handle 2 parallel requests

# ComfyUI memory mode
COMFYUI_CLI_ARGS=--normalvram   # Options: --normalvram, --lowvram, --highvram
```

### VRAM Allocation Strategy

| Service | Max VRAM | Purpose |
|---------|----------|---------|
| **Ollama** | ~10 GB | LLM inference (chat) |
| **ComfyUI** | ~6 GB | Image generation (uses remaining VRAM + RAM) |

---

## Tuning for Different Workloads

### Chat-Heavy (Many Users, Larger Models)

```bash
OLLAMA_MAX_VRAM=12884901888     # 12 GB for Ollama
OLLAMA_MAX_LOADED_MODELS=3
VRAM_THRESHOLD=70               # More proactive freeing
```

### Image-Heavy (Complex Workflows, Video)

```bash
OLLAMA_MAX_VRAM=8589934592      # 8 GB for Ollama
COMFYUI_CLI_ARGS=--highvram     # Keep models in VRAM
VRAM_THRESHOLD=85               # Less aggressive freeing
```

### Both Services Struggling

```bash
OLLAMA_MAX_VRAM=7516192768      # 7 GB for Ollama
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_NUM_PARALLEL=1
COMFYUI_CLI_ARGS=--lowvram      # Aggressive memory saving
VRAM_THRESHOLD=65
VRAM_CHECK_INTERVAL=3
```

After changing settings, restart the stack:

```bash
docker compose -f docker-compose.dev.yaml down
docker compose -f docker-compose.dev.yaml up -d
```

---

## Model Size Reference

### Ollama LLM Models (approximate VRAM)

| Size | Examples | VRAM Usage |
|------|----------|------------|
| 7B | Mistral, Llama2-7B, Phi-3 | 4–5 GB |
| 13B | Llama2-13B, Vicuna-13B | 7–8 GB |
| 30B+ | Llama2-70B Q4, CodeLlama-34B Q4 | 10–15 GB |

### ComfyUI Workflows (approximate VRAM)

| Workflow | VRAM Usage |
|----------|------------|
| Simple SDXL | 3–4 GB |
| Flux | 4–6 GB |
| Multiple LoRAs | +1–2 GB each |
| ControlNet | +1–2 GB |
| Video (AnimateDiff) | 8–10 GB |

---

## Monitoring

```bash
# VRAM Manager logs
docker logs -f aistack-vram-manager

# GPU usage (real-time)
watch -n 1 nvidia-smi

# Container resource usage
docker stats aistack-ollama aistack-comfyui aistack-vram-manager

# Count memory frees
docker logs aistack-vram-manager | grep "Freed ComfyUI memory" | wc -l

# Check for errors
docker logs aistack-vram-manager | grep ERROR

# Verify Ollama environment
docker inspect aistack-ollama | grep -A 10 "Env"
```

---

## Performance Expectations

| Operation | Expected Time |
|-----------|---------------|
| Chat response (7B) | 1–3 seconds |
| Chat response (13B) | 2–5 seconds |
| SDXL image (512×512) | 3–8 seconds |
| SDXL image (1024×1024) | 8–15 seconds |
| Video generation | 2–5 minutes (uses RAM) |

### Concurrent Load

- **2–3 chat + 1 image**: ✅ Works well
- **5 chat users**: ✅ Queue forms but manageable
- **2+ simultaneous images**: ⚠️ May cause slowdown
- **13B+ model + image gen**: ✅ VRAM Manager handles it

---

## Troubleshooting

### Ollama Falls Back to CPU (Very Slow Responses)

```bash
# Check if Ollama is using GPU
docker logs aistack-ollama | grep -E "VRAM|offload"

# Check VRAM usage
nvidia-smi

# Manually free ComfyUI memory
docker exec aistack-comfyui curl -X POST http://localhost:8188/free \
  -H "Content-Type: application/json" \
  -d '{"unload_models": true, "free_memory": true}'
```

### VRAM Manager Not Freeing Memory

```bash
# Enable debug logging
# Set VRAM_DEBUG=true in .env.dev, then:
docker compose -f docker-compose.dev.yaml restart vram-manager
docker logs -f aistack-vram-manager
```

Common causes:
- Check interval too long → try `VRAM_CHECK_INTERVAL=2`
- Threshold too high → try `VRAM_THRESHOLD=70`
- Rate limiting → 30s minimum between frees (by design)

### Container Won't Start

```bash
# Check logs
docker logs aistack-vram-manager

# Verify services are reachable from inside the container
docker exec aistack-vram-manager curl http://aistack-ollama:11434/api/tags
docker exec aistack-vram-manager curl http://aistack-comfyui:8188/system_stats

# Verify all containers are on the same network
docker network inspect ai-stack-network | grep -A 5 "Containers"
```

### ComfyUI Out of Memory

```bash
# Switch to low VRAM mode
# Set COMFYUI_CLI_ARGS=--lowvram in .env.dev

# Or reduce Ollama's allocation
# Set OLLAMA_MAX_VRAM=8589934592 in .env.dev (8 GB)

# Then restart
docker compose -f docker-compose.dev.yaml down
docker compose -f docker-compose.dev.yaml up -d
```

### Services Won't Start (GPU Not Found)

```bash
# Check GPU is accessible
nvidia-smi

# Verify Docker GPU support
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

---

## API Endpoints Used

### Ollama

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/tags` | List available models |
| GET | `/api/ps` | List running/loaded models |

### ComfyUI

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/system_stats` | System status |
| POST | `/free` | Free memory (`{"unload_models": bool, "free_memory": true}`) |

---

## Resources

- [Ollama Configuration FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.md)
- [ComfyUI CLI Arguments](https://github.com/comfyanonymous/ComfyUI)
- [ComfyUI API Docs](https://github.com/comfyanonymous/ComfyUI/blob/master/API.md)
- [NVIDIA SMI Documentation](https://developer.nvidia.com/nvidia-system-management-interface)
- [Docker GPU Support](https://docs.docker.com/config/containers/resource_constraints/#gpu)
