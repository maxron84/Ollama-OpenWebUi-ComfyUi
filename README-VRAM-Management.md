# VRAM Management - Quick Reference

This project provides intelligent VRAM management for your 16GB GPU running both Ollama and ComfyUI.

## 🎯 Approach: Balanced Configuration + Automatic Management

The system uses a single balanced configuration combined with automatic dynamic VRAM management via a Docker service to handle all workload scenarios.

### Configuration (`.env.dev`)

**Static Allocation:**
- **Ollama:** 10GB VRAM, 2 models loaded, 2 parallel requests
- **ComfyUI:** 6GB VRAM, --normalvram mode (dynamic memory management)

This balanced allocation works for:
- ✅ Daily operations with ~5 concurrent users
- ✅ Mixed chat and image generation
- ✅ 7B-13B language models
- ✅ Standard image workflows
- ✅ Simple to moderate ComfyUI workflows

---

## 🤖 Automatic VRAM Manager (Docker Service)

The VRAM Manager runs as a Docker service alongside Ollama and ComfyUI, automatically optimizing VRAM allocation in real-time by monitoring both services and freeing ComfyUI's memory when Ollama needs to load models.

### How It Works

```
┌──────────────────────────────────────────────────┐
│    VRAM Manager Container (monitors every 5s)    │
└──────────────────────────────────────────────────┘
                    │
      ┌─────────────┴─────────────┐
      ▼                           ▼
┌──────────┐              ┌──────────────┐
│  Ollama  │              │   ComfyUI    │
│ New model│              │ Free memory  │
│ loading? │──── YES ────▶│ via /free API│
└──────────┘              └──────────────┘
      │                           │
      ▼                           ▼
Ollama stays on GPU    ComfyUI releases VRAM
(prevents CPU fallback)  (cache + models)
```

### Key Features

- **Prevents CPU Fallback**: Automatically frees VRAM so Ollama stays on GPU (100x faster than CPU)
- **Two-Stage Freeing**: Soft free (cache) first, aggressive (unload models) if needed
- **Rate Limited**: Won't free more than once every 30 seconds
- **VRAM Threshold**: Triggers when usage exceeds 75% (configurable)
- **Minimal Overhead**: <1% CPU, ~50MB RAM
- **Integrated**: Starts/stops with docker-compose
- **Docker Native**: Uses Docker networking and logging

### Quick Setup

The VRAM manager is **integrated** into [`docker-compose.dev.yaml`](docker-compose.dev.yaml) and starts automatically with the stack:

```bash
# Start all services including VRAM manager
docker compose -f docker-compose.dev.yaml up -d
```

That's it! No separate deployment needed.

**Alternative deployment options** are available in [`generated/`](generated/README.md) for custom setups.

### Configuration Options

Add to `.env.dev`:

```bash
VRAM_MANAGER_CONTAINER_NAME=aistack-vram-manager
VRAM_CHECK_INTERVAL=5          # Check interval in seconds
VRAM_THRESHOLD=75              # Free ComfyUI when VRAM exceeds this %
VRAM_DEBUG=false               # Enable debug logging
```

---

## 🚀 Getting Started

### 1. Start Services with Balanced Configuration

```bash
# Use the balanced configuration (already set as default)
docker compose -f docker-compose.dev.yaml up -d

# Verify services are running
docker compose -f docker-compose.dev.yaml ps
```

### 2. Verify VRAM Manager is Running

The VRAM manager starts automatically with the stack:

```bash
# Check it's running
docker ps | grep vram-manager

# Should show: aistack-vram-manager
```

### 3. Monitor Operation

```bash
# Watch GPU usage in real-time
watch -n 1 nvidia-smi

# View VRAM manager logs
docker logs -f aistack-vram-manager

# Check service stats
docker stats aistack-ollama aistack-comfyui aistack-vram-manager
```

---

## 📊 What This Setup Handles

### Automatically Handles

| Scenario | How It's Handled |
|----------|-----------------|
| **Chat-heavy load** (5+ users) | Ollama uses its 10GB allocation, models load/unload as needed |
| **Image generation** | ComfyUI uses 6GB + system RAM as needed (--normalvram) |
| **New model loading** | VRAM manager frees ComfyUI memory automatically |
| **Video generation** | ComfyUI swaps to RAM for large models, slower but works |
| **Mixed workload** | Both services share GPU dynamically |
| **VRAM pressure** | VRAM manager triggers at 75% threshold |

### Performance Expectations

| Operation | Performance |
|-----------|-------------|
| **Chat (7B model)** | 1-2 seconds |
| **Chat (13B model)** | 2-4 seconds |
| **Simple image (SDXL)** | 5-10 seconds |
| **Complex image (3+ LoRAs)** | 15-30 seconds |
| **Video generation** | 2-5 minutes (uses RAM) |
| **Concurrent users** | 3-5 chat + 1-2 images |

---

## 🔧 Tuning for Specific Workloads

If you have specific requirements, adjust these settings:

### For Chat-Heavy Workload (Many Users, Larger Models)

```bash
# In .env.dev, increase Ollama allocation:
OLLAMA_MAX_VRAM=12884901888  # 12GB instead of 10GB
OLLAMA_MAX_LOADED_MODELS=3   # Keep 3 models loaded

# Adjust VRAM manager to be more proactive:
VRAM_THRESHOLD=70
```

### For Image-Heavy Workload (Complex Workflows, Videos)

```bash
# In .env.dev, give ComfyUI more memory and switch to highvram:
OLLAMA_MAX_VRAM=8589934592   # 8GB for Ollama
COMFYUI_CLI_ARGS=--highvram  # Keep models in VRAM

# Adjust VRAM manager to be less aggressive:
VRAM_THRESHOLD=85
```

---

## 📚 Documentation

- **[Docker Service Options](generated/README.md)** - Two Docker deployment options
  - Option 1: Dockerfile (Production)
  - Option 2: No Build (Development)
  
- **[VRAM Management Guide](docs/VRAM-Management-Guide.md)** - Comprehensive tuning guide
  - Configuration options
  - Performance optimization
  - Model size reference
  - Troubleshooting steps

- **[Automatic VRAM Management](docs/Automatic-VRAM-Management.md)** - Deep dive into the VRAM manager
  - How it works
  - API integration details
  - Monitoring and tuning
  - Advanced usage

---

## 🔍 Monitoring Commands

### Check Current Status

```bash
# GPU usage
nvidia-smi

# All container stats
docker stats

# VRAM manager logs
docker logs -f aistack-vram-manager

# Check VRAM configuration
docker inspect aistack-ollama | grep OLLAMA_MAX_VRAM
docker inspect aistack-comfyui | grep CLI_ARGS
```

### Troubleshooting

```bash
# If Ollama is slow (check if it fell back to CPU)
docker logs aistack-ollama | grep -E "VRAM|CPU|offload"

# If ComfyUI has issues
docker logs aistack-comfyui | tail -50

# If VRAM manager isn't working
docker logs aistack-vram-manager
docker exec aistack-vram-manager curl http://aistack-ollama:11434/api/tags
docker exec aistack-vram-manager curl http://aistack-comfyui:8188/system_stats
```

---

## ✅ Benefits of This Approach

**Vs. Manual VRAM Management:**
- ✅ No manual intervention required
- ✅ Handles unexpected workload changes automatically
- ✅ Prevents Ollama CPU fallback
- ✅ Simpler configuration (one profile)
- ✅ Integrated with Docker Compose

**Vs. No VRAM Management:**
- ✅ 100x better performance (GPU vs CPU)
- ✅ Fewer out-of-memory errors
- ✅ Better user experience for all users
- ✅ Automatic optimization

**System Requirements:**
- ✅ Docker and Docker Compose
- ✅ <1% additional CPU overhead
- ✅ ~50MB additional RAM

---

## 🎯 Summary

This VRAM management system provides:

✅ **Single balanced configuration** - Works for all scenarios
✅ **Automatic dynamic optimization** - Docker service handles it
✅ **Prevents CPU fallback** - Ollama stays on GPU
✅ **Intelligent memory freeing** - ComfyUI releases VRAM when needed
✅ **Minimal overhead** - <1% CPU, 50MB RAM
✅ **Docker native** - Starts/stops with compose
✅ **Simple to maintain** - One configuration, one Docker service

**Recommended setup for most users:**
```bash
# Start all services (VRAM manager included)
docker compose -f docker-compose.dev.yaml up -d
```

That's it! The system will handle VRAM optimization automatically.

**Note:** Alternative deployment options (Dockerfile-based, custom configurations) are available in the [`generated/`](generated/README.md) directory for advanced use cases.