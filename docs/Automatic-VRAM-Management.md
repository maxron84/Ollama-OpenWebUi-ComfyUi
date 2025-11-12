# Automatic VRAM Management

## Overview

The VRAM Manager is a Python script that runs as a Docker service, automatically monitoring Ollama and ComfyUI and freeing ComfyUI's VRAM when Ollama needs to load models. This prevents Ollama from falling back to CPU mode when VRAM is full.

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
    │   Check PS   │            │  Check Stats │
    └──────────────┘            └──────────────┘
            │                            │
            ▼                            │
    New model loading?                   │
            │                            │
            ├─── YES ────────────────────┤
            │                            ▼
            │                   Call ComfyUI /free API
            │                   - Free memory cache
            │                   - Unload models if needed
            │                            │
            │                            ▼
            │                   ComfyUI releases VRAM
            │                            │
            ▼                            ▼
    Ollama loads model using freed VRAM
```

### Triggers for Freeing ComfyUI VRAM

1. **New Ollama Model Loading**: When a new model is detected in Ollama's process list
2. **VRAM Threshold Exceeded**: When total VRAM usage exceeds configured threshold (default 75%)
3. **Rate Limited**: Won't free more than once every 30 seconds to avoid thrashing

### Two-Stage Freeing Strategy

1. **Soft Free** (default): Clears ComfyUI's memory cache only
2. **Aggressive Free** (if needed): Fully unloads models if VRAM still above 85%

---

## Docker Deployment

The VRAM manager runs as a Docker container integrated with your docker-compose setup. Two deployment options are available:

### Option 1: Dockerfile (Production)

**Best for:** Production deployments, stable environments

```bash
# Build the image
docker build -f generated/option1-dockerfile/Dockerfile.vram-manager -t vram-manager:latest .

# Start with docker-compose
docker compose -f docker-compose.dev.yaml -f generated/option1-dockerfile/docker-compose.vram-manager.yaml up -d
```

**Benefits:**
- ✅ Fast startup (~2 seconds)
- ✅ Optimized image (~50MB)
- ✅ Dependencies pre-installed
- ✅ Production-ready

📚 **[Full setup guide](../generated/option1-dockerfile/README.md)**

### Option 2: No Build (Development)

**Best for:** Development, testing, quick setup

```bash
# Start directly (no build needed)
docker compose -f docker-compose.dev.yaml -f generated/option2-no-build/docker-compose.vram-manager.yaml up -d
```

**Benefits:**
- ✅ No build step required
- ✅ Script mounted (edit without rebuild)
- ✅ Perfect for testing
- ✅ Faster to get started

📚 **[Full setup guide](../generated/option2-no-build/README.md)**

### Comparison

| Feature | Option 1 (Dockerfile) | Option 2 (No Build) |
|---------|----------------------|---------------------|
| **Startup Time** | ~2 seconds | ~5 seconds |
| **Build Required** | Yes | No |
| **Image Size** | ~50MB | ~150MB base |
| **Script Editing** | Requires rebuild | Live (mounted) |
| **Best For** | Production | Development |

📚 **[Detailed comparison](../generated/README.md)**

---

## Configuration

### Environment Variables

Add to `.env.dev`:

```bash
# VRAM Manager Configuration
VRAM_MANAGER_CONTAINER_NAME=aistack-vram-manager
VRAM_CHECK_INTERVAL=5          # Check interval in seconds
VRAM_THRESHOLD=75              # Free ComfyUI when VRAM exceeds this %
VRAM_DEBUG=false               # Enable debug logging
```

### Tuning Parameters

#### Check Interval

```bash
# More responsive (check every 2 seconds)
VRAM_CHECK_INTERVAL=2

# Less CPU overhead (check every 10 seconds)
VRAM_CHECK_INTERVAL=10
```

**Recommendation:** 
- Development: 2-5 seconds
- Production: 5-10 seconds

#### VRAM Threshold

```bash
# More aggressive (free at 70%)
VRAM_THRESHOLD=70

# More conservative (free at 85%)
VRAM_THRESHOLD=85
```

**Recommendation:**
- Balanced mode: 75% (default)
- Chat-heavy: 70% (more proactive)
- Image-heavy: 85% (let ComfyUI use more)

---

## Monitoring

### Real-time Monitoring

```bash
# Watch VRAM manager logs
docker logs -f aistack-vram-manager

# Watch GPU usage
watch -n 1 nvidia-smi

# Watch both in split terminal
# Terminal 1:
docker logs -f aistack-vram-manager

# Terminal 2:
watch -n 1 nvidia-smi
```

### Log Analysis

```bash
# Check how many times memory was freed
docker logs aistack-vram-manager | grep "Freed ComfyUI memory"

# Check for errors
docker logs aistack-vram-manager | grep ERROR

# Export logs to file
docker logs aistack-vram-manager --since "1 day ago" > vram-manager.log

# Follow logs with timestamp
docker logs -f --timestamps aistack-vram-manager
```

### Container Stats

```bash
# Monitor resource usage
docker stats aistack-vram-manager

# Check if container is running
docker ps | grep vram-manager

# View container details
docker inspect aistack-vram-manager
```

---

## Integration with VRAM Profiles

### With Balanced Mode (Recommended)

```bash
# 1. Use balanced configuration
docker compose -f docker-compose.dev.yaml up -d

# 2. Start VRAM manager (choose option 1 or 2)
docker compose -f docker-compose.dev.yaml -f generated/option2-no-build/docker-compose.vram-manager.yaml up -d

# Result: Automatic VRAM optimization for mixed workload
```

### Tuning for Chat-Heavy Workload

```bash
# In .env.dev
OLLAMA_MAX_VRAM=12884901888  # 12GB for Ollama
VRAM_THRESHOLD=70             # More proactive freeing

# Restart services
docker compose restart ollama vram-manager
```

### Tuning for Image-Heavy Workload

```bash
# In .env.dev
OLLAMA_MAX_VRAM=8589934592    # 8GB for Ollama
COMFYUI_CLI_ARGS=--highvram   # ComfyUI gets priority
VRAM_THRESHOLD=85             # Less aggressive freeing

# Restart services
docker compose restart ollama comfyui vram-manager
```

---

## Troubleshooting

### Container Won't Start

**Problem:** VRAM manager container fails to start

```bash
# Check container logs
docker logs aistack-vram-manager

# Check if services are accessible
docker exec aistack-vram-manager curl http://aistack-ollama:11434/api/tags
docker exec aistack-vram-manager curl http://aistack-comfyui:8188/system_stats

# Verify network
docker network inspect ai-stack-network

# Check depends_on conditions
docker compose ps
```

**Solution:** Ensure both Ollama and ComfyUI are healthy before starting VRAM manager.

### Not Freeing Memory

**Problem:** VRAM manager runs but doesn't free memory

```bash
# Enable debug logging in .env.dev
VRAM_DEBUG=true

# Restart and watch logs
docker compose restart vram-manager
docker logs -f aistack-vram-manager

# Check if it detects model loads
# Watch for: "New Ollama model(s) detected"
```

**Common causes:**
1. Check interval too long (try `VRAM_CHECK_INTERVAL=2`)
2. VRAM threshold too high (try `VRAM_THRESHOLD=70`)
3. Rate limiting (30s minimum between frees)

### Network Issues

**Problem:** Can't connect to Ollama or ComfyUI

```bash
# Test connectivity from inside container
docker exec aistack-vram-manager ping aistack-ollama
docker exec aistack-vram-manager ping aistack-comfyui

# Check if using correct URLs
docker exec aistack-vram-manager curl http://aistack-ollama:11434/api/tags
docker exec aistack-vram-manager curl http://aistack-comfyui:8188/system_stats

# Verify all containers on same network
docker network inspect ai-stack-network | grep -A 5 "Containers"
```

### High CPU Usage

**Problem:** VRAM manager uses too much CPU

**Solution:** Increase check interval
```bash
# In .env.dev
VRAM_CHECK_INTERVAL=10  # Instead of 5

# Restart
docker compose restart vram-manager
```

---

## API Endpoints Used

### Ollama APIs

```bash
# Check available models
GET http://aistack-ollama:11434/api/tags

# Check running models
GET http://aistack-ollama:11434/api/ps
```

### ComfyUI APIs

```bash
# Get system stats
GET http://aistack-comfyui:8188/system_stats

# Free memory (soft)
POST http://aistack-comfyui:8188/free
{
  "unload_models": false,
  "free_memory": true
}

# Free memory (aggressive)
POST http://aistack-comfyui:8188/free
{
  "unload_models": true,
  "free_memory": true
}
```

---

## Advanced Usage

### Manual Memory Management

You can manually trigger ComfyUI memory freeing:

```bash
# Soft free (cache only)
docker exec aistack-comfyui curl -X POST http://localhost:8188/free \
  -H "Content-Type: application/json" \
  -d '{"unload_models": false, "free_memory": true}'

# Aggressive free (unload models)
docker exec aistack-comfyui curl -X POST http://localhost:8188/free \
  -H "Content-Type: application/json" \
  -d '{"unload_models": true, "free_memory": true}'
```

### Custom Script Modifications

For Option 2 (No Build), you can edit the script directly:

```bash
# Edit script
nano scripts/vram-manager.py

# Restart to apply changes
docker compose restart vram-manager

# Watch logs for changes
docker logs -f aistack-vram-manager
```

For Option 1 (Dockerfile), rebuild after changes:

```bash
# Edit script
nano scripts/vram-manager.py

# Rebuild image
docker build -f generated/option1-dockerfile/Dockerfile.vram-manager -t vram-manager:latest .

# Restart container
docker compose restart vram-manager
```

### Integration with Monitoring Systems

```bash
# Export logs to monitoring system
docker logs aistack-vram-manager 2>&1 | \
  grep "Freed ComfyUI" | \
  while read line; do
    # Send to webhook, logging system, etc.
    curl -X POST https://your-monitoring-system.com/log \
      -d "message=$line"
  done
```

---

## Best Practices

1. **Start with Option 2 for testing** - Easy to adjust and iterate
2. **Switch to Option 1 for production** - Faster and more efficient
3. **Monitor for first few days** - Check logs to see how often it's freeing memory
4. **Tune thresholds based on usage** - Adjust based on your actual patterns
5. **Use Docker logs** - More reliable than file-based logging
6. **Don't over-tune** - The defaults work well for most cases

---

## Performance Impact

### VRAM Manager Overhead

- **CPU Usage:** <1% (with 5-second interval)
- **Memory Usage:** ~30-50MB
- **Network:** Minimal (local API calls only)
- **Disk I/O:** Minimal (logs only)
- **Latency Added:** 0-5 seconds (detection time)

### Benefits

- **Prevents Ollama CPU fallback:** Massive performance gain (100x)
- **Automatic optimization:** No manual intervention needed
- **Reduced OOM errors:** Proactive memory management
- **Improved user experience:** Smoother operation for all users
- **Docker native:** Integrates seamlessly with compose

---

## Comparison: Manual vs Automatic vs Docker

| Aspect | Manual Switching | Automatic (Script) | Docker Service |
|--------|-----------------|-------------------|----------------|
| **Setup** | Simple | Manual install | docker-compose |
| **Flexibility** | Full control | Automatic | Automatic |
| **Integration** | Separate | Separate | Native |
| **Logging** | Various | File/journal | Docker logs |
| **Management** | Manual | systemd | Docker |
| **Best For** | Predictable loads | Ad-hoc setups | Production |

---

## When to Use What

### Use Docker Service (Recommended)

- ✅ Production deployments
- ✅ Docker-based infrastructure
- ✅ Integrated monitoring needed
- ✅ Easy management via compose
- ✅ Consistent with other services

### Use Manual Script (Alternative)

- ⚠️ Non-Docker environments
- ⚠️ Custom deployment needs
- ⚠️ Special requirements

---

## Summary

The VRAM Manager Docker service provides:

✅ **Automatic VRAM optimization** - No manual intervention
✅ **Prevents CPU fallback** - Keeps Ollama on GPU
✅ **Minimal overhead** - <1% CPU, 50MB RAM
✅ **Docker native** - Integrates with compose
✅ **Production-ready** - Two deployment options
✅ **Configurable** - Tune for your needs
✅ **Easy monitoring** - Docker logs integration

Start with balanced mode + VRAM manager Docker service for most use cases, then tune based on your specific requirements.