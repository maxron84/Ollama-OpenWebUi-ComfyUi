# VRAM Management Guide

## Overview

This guide explains how to manage GPU VRAM allocation between Ollama and ComfyUI on a 16GB GPU system with ~5 concurrent users.

## Current Configuration (16GB GPU)

### Allocation Strategy

| Service | Max VRAM | Purpose | Dynamic Behavior |
|---------|----------|---------|-----------------|
| **Ollama** | ~10GB | LLM inference (chat) | Loads/unloads models on-demand |
| **ComfyUI** | ~6GB | Image generation | Uses remaining VRAM dynamically |

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

**Memory modes available:**
- `--normalvram`: Balanced mode (recommended) - moves models between VRAM/RAM as needed
- `--lowvram`: Aggressive memory saving - uses system RAM when VRAM full (slower)
- `--novram`: Extreme compatibility - keeps models in system RAM (very slow)
- `--highvram`: Performance mode - keeps everything in VRAM (uses more memory)

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

### Check Current Configuration

```bash
# Verify Ollama environment variables
docker inspect aistack-ollama | grep -A 10 "Env"

# Verify ComfyUI CLI args
docker inspect aistack-comfyui | grep CLI_ARGS
```

## Model Size Reference

Understanding model VRAM requirements helps with capacity planning:

### Ollama LLM Models (approximate VRAM usage)

| Model Size | Example Models | VRAM Usage | Notes |
|------------|---------------|------------|-------|
| 7B | Mistral, Llama2-7B, Phi-3 | 4-5GB | Fast, fits 2 models |
| 13B | Llama2-13B, Vicuna-13B | 7-8GB | Good balance |
| 30B+ | Llama2-70B, CodeLlama-34B | 15GB+ | May not fit with ComfyUI |

### ComfyUI Workflows (approximate VRAM usage)

| Workflow Type | VRAM Usage | Notes |
|---------------|------------|-------|
| Simple SDXL | 3-4GB | Basic image generation |
| Flux | 4-6GB | Advanced model |
| Multiple LoRAs | +1-2GB each | Additive memory usage |
| ControlNet | +1-2GB | Additional control |

## Tuning Guidelines

### Scenario 1: Ollama Out of Memory (OOM)

**Symptoms:**
- Model loading fails
- "Out of memory" errors in logs
- Requests timeout or fail

**Solutions:**
```bash
# Option A: Reduce VRAM allocation
OLLAMA_MAX_VRAM=8589934592  # 8GB instead of 10GB

# Option B: Reduce loaded models
OLLAMA_MAX_LOADED_MODELS=1  # Only keep 1 model loaded

# Option C: Reduce parallel requests
OLLAMA_NUM_PARALLEL=1       # Process requests sequentially
```

### Scenario 2: ComfyUI Out of Memory

**Symptoms:**
- Image generation fails
- ComfyUI becomes unresponsive
- CUDA out of memory errors

**Solutions:**
```bash
# Option A: Switch to low VRAM mode
COMFYUI_CLI_ARGS=--lowvram

# Option B: Use no VRAM mode (slowest but safest)
COMFYUI_CLI_ARGS=--novram

# Option C: Reduce Ollama allocation to give ComfyUI more space
OLLAMA_MAX_VRAM=8589934592  # 8GB for Ollama, ~8GB for ComfyUI
```

### Scenario 3: Both Services Struggling

**Symptoms:**
- Both services showing OOM errors
- GPU at 100% memory constantly
- Slow performance overall

**Solutions:**
```bash
# Aggressive memory management
OLLAMA_MAX_VRAM=7516192768   # 7GB for Ollama
OLLAMA_MAX_LOADED_MODELS=1   # Single model only
OLLAMA_NUM_PARALLEL=1        # Sequential processing
COMFYUI_CLI_ARGS=--lowvram   # Aggressive ComfyUI memory saving
```

### Scenario 4: Need Larger Models

**For 13B+ models:**
```bash
OLLAMA_MAX_VRAM=12884901888  # 12GB for Ollama
OLLAMA_MAX_LOADED_MODELS=1   # Single large model
COMFYUI_CLI_ARGS=--lowvram   # ComfyUI uses minimal VRAM
```

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

### Problem: One Service Monopolizing GPU

```bash
# Check which process is using memory
nvidia-smi pmon -c 1

# Restart the problematic service
docker restart aistack-ollama
# or
docker restart aistack-comfyui
```

### Problem: Frequent Model Reloading (Ollama)

**Symptom:** Models constantly loading/unloading, slow responses

**Solution:** Increase max loaded models if you have VRAM headroom:
```bash
OLLAMA_MAX_LOADED_MODELS=2  # or 3 for small models
```

### Problem: ComfyUI Too Slow

**Symptom:** Image generation takes very long

**Solution:** Switch to normal or high VRAM mode:
```bash
COMFYUI_CLI_ARGS=--normalvram  # or --highvram if VRAM available
```

## Testing Your Configuration

### Step 1: Start Services

```bash
docker compose -f docker-compose.dev.yaml up -d
```

### Step 2: Monitor Startup

```bash
# Watch GPU usage during startup
watch -n 1 nvidia-smi

# Check both services are healthy
docker compose -f docker-compose.dev.yaml ps
```

### Step 3: Test Ollama

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

### Step 4: Test ComfyUI

1. Open http://localhost:8188
2. Load a workflow
3. Generate an image
4. Monitor VRAM usage with `nvidia-smi`

### Step 5: Test Concurrent Usage

1. Start a chat session in Open-WebUI
2. Start an image generation in ComfyUI
3. Monitor GPU memory allocation
4. Verify both complete successfully

## Performance Expectations

### Expected Response Times (with 16GB GPU)

| Operation | Expected Time | Notes |
|-----------|---------------|-------|
| Ollama model load | 2-5 seconds | First request only |
| Chat response (7B) | 1-3 seconds | After model loaded |
| Chat response (13B) | 2-5 seconds | After model loaded |
| SDXL image (512x512) | 3-8 seconds | Depends on steps |
| SDXL image (1024x1024) | 8-15 seconds | Depends on steps |

### Concurrent Load Performance

- **2-3 chat users + 1 image generation**: ✅ Should work well
- **5 chat users simultaneously**: ✅ Queue forms but manageable
- **2+ image generations simultaneously**: ⚠️ May cause slowdown
- **Heavy 13B+ model + image generation**: ⚠️ May cause memory pressure

## Advanced Configuration

### Dynamic Scaling Based on Usage Patterns

If you notice one service is used more than the other:

**Chat-heavy workload:**
```bash
OLLAMA_MAX_VRAM=12884901888  # 12GB for Ollama
OLLAMA_MAX_LOADED_MODELS=2   # Keep multiple models
COMFYUI_CLI_ARGS=--lowvram   # ComfyUI uses less
```

**Image-heavy workload:**
```bash
OLLAMA_MAX_VRAM=7516192768   # 7GB for Ollama
OLLAMA_MAX_LOADED_MODELS=1   # Single model
COMFYUI_CLI_ARGS=--highvram  # ComfyUI gets priority
```

### Time-based Optimization

For predictable usage patterns, consider:
- Peak hours: Balanced allocation (current config)
- Off-peak: Allow more VRAM for better performance
- Scheduled model preloading before peak times

## Applying Changes

After modifying configuration:

```bash
# Stop services
docker compose -f docker-compose.dev.yaml down

# Start with new configuration
docker compose -f docker-compose.dev.yaml up -d

# Verify changes took effect
docker inspect aistack-ollama | grep -E "OLLAMA_MAX_VRAM|MAX_LOADED"
docker inspect aistack-comfyui | grep CLI_ARGS
```

## Support and Resources

- [Ollama Configuration](https://github.com/ollama/ollama/blob/main/docs/faq.md)
- [ComfyUI Command Line Arguments](https://github.com/comfyanonymous/ComfyUI)
- [NVIDIA SMI Documentation](https://developer.nvidia.com/nvidia-system-management-interface)
- [Docker GPU Support](https://docs.docker.com/config/containers/resource_constraints/#gpu)

## Summary

The configured VRAM management strategy provides:

✅ **Balanced allocation** for 5 concurrent users
✅ **Automatic memory management** via model loading/unloading
✅ **Flexibility** to tune based on actual usage patterns
✅ **Monitoring tools** to track performance
✅ **Clear guidelines** for troubleshooting

Start with the default configuration and adjust based on your actual usage patterns and user feedback.
