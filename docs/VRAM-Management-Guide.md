# VRAM Management Guide

## Overview

This guide explains how to manage GPU VRAM allocation between Ollama and ComfyUI on a 16GB GPU system with ~5 concurrent users.

## Approach: Balanced Configuration + Automatic Management

The system uses a single balanced static allocation combined with an automatic VRAM manager that dynamically optimizes memory usage in real-time.

---

## Balanced Configuration

### Overview
A single configuration optimized for mixed workloads with ~5 concurrent users doing both chat and image generation, enhanced by automatic VRAM management.

### Allocation Strategy

| Service | Max VRAM | Purpose | Dynamic Behavior |
|---------|----------|---------|-----------------|
| **Ollama** | ~10GB | LLM inference (chat) | Loads/unloads models on-demand |
| **ComfyUI** | ~6GB | Image generation | Uses remaining VRAM + RAM dynamically |

### Ollama Settings

```bash
OLLAMA_MAX_VRAM=10737418240          # 10GB max VRAM allocation
OLLAMA_MAX_LOADED_MODELS=2           # Keep max 2 models in memory
OLLAMA_NUM_PARALLEL=2                # Handle 2 parallel requests
```

**How it works:**
- Models load on-demand when users send requests
- When VRAM limit is reached, oldest unused models unload automatically
- Limits concurrent models to prevent memory exhaustion
- Allows 2 parallel requests for better throughput with 5 users

### ComfyUI Settings

```bash
COMFYUI_CLI_ARGS=--normalvram        # Balanced memory mode
```

**Memory mode:**
- `--normalvram`: Balanced mode (recommended) - moves models between VRAM/RAM as needed

This allows ComfyUI to handle complex workflows by using system RAM when VRAM is full.

---

## Automatic VRAM Manager

### Overview

The VRAM Manager (`scripts/vram-manager.py`) monitors both services and automatically frees ComfyUI's VRAM when Ollama needs to load models. This **prevents Ollama from falling back to CPU mode** (which would be 100x slower).

### How It Works

```
Monitor Ollama (every 5s) → Detect new model loading → Call ComfyUI /free API → ComfyUI releases VRAM → Ollama loads model on GPU
```

### Triggers

1. **New Model Loading**: When Ollama starts loading a new model
2. **VRAM Threshold**: When total GPU VRAM usage exceeds 75% (configurable)
3. **Rate Limited**: Minimum 30 seconds between frees to avoid thrashing

### Two-Stage Freeing

1. **Soft Free**: Clears ComfyUI's memory cache only
2. **Aggressive Free**: If VRAM still >85%, fully unloads ComfyUI models

### Setup

Two Docker deployment options available:

**Option 1: Dockerfile (Production)**
```bash
docker build -f generated/option1-dockerfile/Dockerfile.vram-manager -t vram-manager:latest .
docker compose -f docker-compose.dev.yaml -f generated/option1-dockerfile/docker-compose.vram-manager.yaml up -d
```

**Option 2: No Build (Development)**
```bash
docker compose -f docker-compose.dev.yaml -f generated/option2-no-build/docker-compose.vram-manager.yaml up -d
```

### Configuration

Add to `.env.dev`:
```bash
VRAM_MANAGER_CONTAINER_NAME=aistack-vram-manager
VRAM_CHECK_INTERVAL=5
VRAM_THRESHOLD=75
VRAM_DEBUG=false
```

📚 **See [Automatic VRAM Management Guide](Automatic-VRAM-Management.md) and [Docker Options](../generated/README.md) for complete documentation**

---

## Monitoring VRAM Usage

### Real-time GPU Monitoring

```bash
# Watch GPU usage in real-time (updates every second)
watch -n 1 nvidia-smi

# Check specific process GPU memory
nvidia-smi --query-compute-apps=pid,used_memory --format=csv
```

### Container Resource Monitoring

```bash
# Monitor all container stats (CPU, Memory, Network)
docker stats

# Monitor specific containers
docker stats aistack-ollama aistack-comfyui

# Follow Ollama logs for VRAM info
docker logs -f aistack-ollama | grep -E "VRAM|loaded|unloaded"

# Follow ComfyUI logs
docker logs -f aistack-comfyui
```

### VRAM Manager Monitoring

```bash
# View VRAM manager logs
docker logs -f aistack-vram-manager

# View recent logs
docker logs aistack-vram-manager --since 10m

# Check container status
docker ps | grep vram-manager

# Count memory frees
docker logs aistack-vram-manager | grep "Freed ComfyUI memory" | wc -l
```

### Check Current Configuration

```bash
# Verify Ollama environment variables
docker inspect aistack-ollama | grep -A 10 "Env"

# Verify ComfyUI CLI args
docker inspect aistack-comfyui | grep CLI_ARGS
```

---

## Model Size Reference

Understanding model VRAM requirements helps with capacity planning:

### Ollama LLM Models (approximate VRAM usage)

| Model Size | Example Models | VRAM Usage | Notes |
|------------|---------------|------------|-------|
| 7B | Mistral, Llama2-7B, Phi-3 | 4-5GB | Fast, can fit 2 models |
| 13B | Llama2-13B, Vicuna-13B | 7-8GB | Good balance |
| 30B+ | Llama2-70B Q4, CodeLlama-34B Q4 | 10-15GB | Need quantized versions |

### ComfyUI Workflows (approximate VRAM usage)

| Workflow Type | VRAM Usage | Notes |
|---------------|------------|-------|
| Simple SDXL | 3-4GB | Basic image generation |
| Flux | 4-6GB | Advanced model |
| Multiple LoRAs | +1-2GB each | Additive memory usage |
| ControlNet | +1-2GB | Additional control |
| Video (AnimateDiff) | 8-10GB | May use system RAM |

---

## Tuning Guidelines

### Scenario 1: Ollama Out of Memory (OOM)

**Symptoms:**
- Model loading fails
- "Out of memory" errors in logs
- Requests timeout or fail

**Solutions:**
```bash
# Option A: Reduce VRAM allocation (in .env.dev)
OLLAMA_MAX_VRAM=8589934592  # 8GB instead of 10GB

# Option B: Reduce loaded models
OLLAMA_MAX_LOADED_MODELS=1  # Only keep 1 model loaded

# Option C: Reduce parallel requests
OLLAMA_NUM_PARALLEL=1       # Process requests sequentially

# Option D: Make VRAM manager more aggressive
python3 scripts/vram-manager.py --vram-threshold 70
```

### Scenario 2: ComfyUI Out of Memory

**Symptoms:**
- Image generation fails
- ComfyUI becomes unresponsive
- CUDA out of memory errors

**Solutions:**
```bash
# Option A: Switch to low VRAM mode (in .env.dev)
COMFYUI_CLI_ARGS=--lowvram

# Option B: Reduce Ollama allocation to give ComfyUI more space
OLLAMA_MAX_VRAM=8589934592  # 8GB for Ollama, ~8GB for ComfyUI

# Option C: Make VRAM manager less aggressive
python3 scripts/vram-manager.py --vram-threshold 85
```

### Scenario 3: Both Services Struggling

**Symptoms:**
- Both services showing OOM errors
- GPU at 100% memory constantly
- Slow performance overall

**Solutions:**
```bash
# Aggressive memory management (in .env.dev)
OLLAMA_MAX_VRAM=7516192768   # 7GB for Ollama
OLLAMA_MAX_LOADED_MODELS=1   # Single model only
OLLAMA_NUM_PARALLEL=1        # Sequential processing
COMFYUI_CLI_ARGS=--lowvram   # Aggressive ComfyUI memory saving

# More proactive VRAM manager
python3 scripts/vram-manager.py --vram-threshold 65 --check-interval 3
```

### Scenario 4: Need for Larger Models (13B+)

**For 13B models:**
```bash
# Give Ollama more VRAM (in .env.dev)
OLLAMA_MAX_VRAM=12884901888  # 12GB for Ollama
OLLAMA_MAX_LOADED_MODELS=1   # Single large model
COMFYUI_CLI_ARGS=--lowvram   # ComfyUI uses minimal VRAM

# More proactive freeing
python3 scripts/vram-manager.py --vram-threshold 70
```

### Scenario 5: Video Generation / Complex Workflows

**For heavy ComfyUI workloads:**
```bash
# Give ComfyUI priority (in .env.dev)
OLLAMA_MAX_VRAM=8589934592   # 8GB for Ollama
COMFYUI_CLI_ARGS=--highvram  # Keep models in VRAM

# Less aggressive freeing
python3 scripts/vram-manager.py --vram-threshold 85
```

---

## Best Practices for 5 Users

### Load Distribution

1. **Stagger Usage**: Not all 5 users will use both services simultaneously
2. **Peak Planning**: Expect 2-3 concurrent chat sessions and 1-2 image generations
3. **Model Selection**: Use 7B models for better concurrency (can fit 2 models)

### User Guidelines

**For Chat Users:**
- Smaller models (7B) provide faster response with better concurrency
- If using 13B+ models, expect longer load times and potential queuing

**For Image Generation Users:**
- Start with simpler workflows to test capacity
- Avoid loading multiple heavy LoRAs simultaneously
- Consider using lower resolution for faster generation
- Video generation will use system RAM (slower but works)

---

## Troubleshooting

### Problem: Services Won't Start

```bash
# Check GPU is accessible
nvidia-smi

# Verify Docker has GPU support
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi

# Check container logs
docker logs aistack-ollama
docker logs aistack-comfyui
```

### Problem: VRAM Manager Not Working

```bash
# Check if services are accessible
curl http://localhost:11434/api/tags
curl http://localhost:8188/system_stats

# Run in debug mode
python3 scripts/vram-manager.py --debug

# Check systemd service
sudo systemctl status vram-manager
sudo journalctl -u vram-manager -n 50
```

### Problem: Ollama Falls Back to CPU

**Symptom:** Very slow responses (100x slower)

```bash
# Check if Ollama is using GPU
docker logs aistack-ollama | grep -E "VRAM|offload"

# Verify VRAM manager is running
sudo systemctl status vram-manager

# Check VRAM usage
nvidia-smi

# Manually free ComfyUI
curl -X POST http://localhost:8188/free \
  -H "Content-Type: application/json" \
  -d '{"unload_models": true, "free_memory": true}'
```

### Problem: Frequent Model Reloading (Ollama)

**Symptom:** Models constantly loading/unloading, slow responses

**Solution:** Increase max loaded models if you have VRAM headroom:
```bash
OLLAMA_MAX_LOADED_MODELS=3  # in .env.dev
```

### Problem: ComfyUI Too Slow

**Symptom:** Image generation takes very long

**Solution:** Check if it's swapping to RAM:
```bash
# Check logs
docker logs aistack-comfyui | tail -50

# If using --lowvram, try --normalvram
COMFYUI_CLI_ARGS=--normalvram  # in .env.dev
```

---

## Testing Your Configuration

### Step 1: Start Services

```bash
docker compose -f docker-compose.dev.yaml up -d
```

### Step 2: Start VRAM Manager

```bash
sudo systemctl start vram-manager
```

### Step 3: Monitor Startup

```bash
# Watch GPU usage during startup
watch -n 1 nvidia-smi

# Check both services are healthy
docker compose -f docker-compose.dev.yaml ps

# Monitor VRAM manager
sudo journalctl -u vram-manager -f
```

### Step 4: Test Ollama

```bash
# Pull a model (if not already available)
docker exec -it aistack-ollama ollama pull mistral

# Run a chat request
curl http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Hello, how are you?",
  "stream": false
}'
```

### Step 5: Test ComfyUI

1. Open http://localhost:8188
2. Load a workflow
3. Generate an image
4. Monitor VRAM usage with `nvidia-smi`

### Step 6: Test Concurrent Usage

1. Start a chat session in Open-WebUI
2. Start an image generation in ComfyUI
3. Monitor GPU memory allocation with `nvidia-smi`
4. Watch VRAM manager logs: `sudo journalctl -u vram-manager -f`
5. Verify both complete successfully

---

## Performance Expectations

### Expected Response Times (with 16GB GPU)

| Operation | Expected Time | Notes |
|-----------|---------------|-------|
| Ollama model load | 2-5 seconds | First request only |
| Chat response (7B) | 1-3 seconds | After model loaded |
| Chat response (13B) | 2-5 seconds | After model loaded |
| SDXL image (512x512) | 3-8 seconds | Depends on steps |
| SDXL image (1024x1024) | 8-15 seconds | Depends on steps |
| Video generation | 2-5 minutes | Uses system RAM |

### Concurrent Load Performance

- **2-3 chat users + 1 image generation**: ✅ Should work well
- **5 chat users simultaneously**: ✅ Queue forms but manageable
- **2+ image generations simultaneously**: ⚠️ May cause slowdown
- **Heavy 13B+ model + image generation**: ✅ VRAM manager handles it

---

## Advanced Configuration

### Adjusting for Chat-Heavy Workload

If your users primarily use chat:

```bash
# In .env.dev
OLLAMA_MAX_VRAM=12884901888  # 12GB for Ollama
OLLAMA_MAX_LOADED_MODELS=3   # Keep more models
OLLAMA_NUM_PARALLEL=4        # More parallel requests

# Adjust VRAM manager
python3 scripts/vram-manager.py --vram-threshold 70
```

### Adjusting for Image-Heavy Workload

If your users primarily generate images:

```bash
# In .env.dev
OLLAMA_MAX_VRAM=8589934592   # 8GB for Ollama
COMFYUI_CLI_ARGS=--highvram  # Keep models in VRAM

# Adjust VRAM manager
python3 scripts/vram-manager.py --vram-threshold 85
```

### Custom VRAM Manager Behavior

Edit the systemd service file:

```bash
sudo nano /etc/systemd/system/vram-manager.service
```

Change parameters in the `ExecStart` line:
```ini
ExecStart=/usr/bin/python3 /path/to/vram-manager.py \
    --check-interval 3 \
    --vram-threshold 70 \
    --debug
```

Then reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart vram-manager
```

---

## Applying Changes

After modifying configuration:

```bash
# Stop services
docker compose -f docker-compose.dev.yaml down

# Start with new configuration
docker compose -f docker-compose.dev.yaml up -d

# Restart VRAM manager if you changed its settings
sudo systemctl restart vram-manager

# Verify changes took effect
docker inspect aistack-ollama | grep -E "OLLAMA_MAX_VRAM|MAX_LOADED"
docker inspect aistack-comfyui | grep CLI_ARGS
sudo systemctl status vram-manager
```

---

## Support and Resources

- [Ollama Configuration](https://github.com/ollama/ollama/blob/main/docs/faq.md)
- [ComfyUI Command Line Arguments](https://github.com/comfyanonymous/ComfyUI)
- [ComfyUI API Documentation](https://github.com/comfyanonymous/ComfyUI/blob/master/API.md)
- [NVIDIA SMI Documentation](https://developer.nvidia.com/nvidia-system-management-interface)
- [Docker GPU Support](https://docs.docker.com/config/containers/resource_constraints/#gpu)

---

## Summary

The configured VRAM management strategy provides:

✅ **Balanced static allocation** for predictable performance
✅ **Automatic dynamic optimization** via VRAM manager
✅ **Prevents CPU fallback** for Ollama (100x performance gain)
✅ **Handles all workload types** without manual intervention
✅ **Production-ready** with systemd service
✅ **Clear monitoring** and troubleshooting tools
✅ **Tunable** for specific use cases

Start with the default balanced configuration + VRAM manager, then tune based on your actual usage patterns.
