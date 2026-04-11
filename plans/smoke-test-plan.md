# Phase 6: Smoke Test Plan

**Target Machine:** RTX 5080 (16 GB VRAM), Ryzen 7 9800X3D, 64 GB DDR5  
**Prerequisites:** Docker Engine + NVIDIA Container Toolkit installed, repo cloned  
**Estimated Time:** 15–20 minutes

---

## Pre-Flight Checks

```bash
# 1. Verify GPU is visible
nvidia-smi

# 2. Verify Docker has GPU access
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi

# 3. Verify Docker Compose is available
docker compose version

# 4. Clone/pull the repo and enter the directory
cd /path/to/Ollama-OpenWebUi-ComfyUi
```

**Expected:** All three commands succeed. `nvidia-smi` shows RTX 5080 with 16 GB. Docker Compose v2.x.

---

## Step 1: Update ComfyUI Image Tag (Phase 3 remainder)

Before starting the stack, research and update the ComfyUI image to the latest available runtime tag:

```bash
# Option A: Browse GHCR packages page
# https://github.com/SaladTechnologies/comfyui-api/pkgs/container/comfyui-api
# Look for the latest tag matching: comfyX.X.X-apiX.X.X-torchX.X.X-cuda12.8-runtime

# Option B: Use Docker CLI (if authenticated)
docker pull ghcr.io/saladtechnologies/comfyui-api:latest
docker image inspect ghcr.io/saladtechnologies/comfyui-api:latest | grep -i tag

# Update the tag in .env.dev:
# COMFYUI_IMAGE=ghcr.io/saladtechnologies/comfyui-api:<new-tag>
#
# And optionally remove the TODO comment in docker-compose.dev.yaml line 95.
```

**If tag research is blocked:** Proceed with the existing tag — it will still work.

---

## Step 2: Start the Stack

```bash
# Copy env file if not already done
cp .env.dev .env

# Pull all images first (so startup is clean)
docker compose -f docker-compose.dev.yaml pull

# Start all services
docker compose -f docker-compose.dev.yaml up -d

# Watch startup progress
docker compose -f docker-compose.dev.yaml logs -f
# (Ctrl+C to exit log follow when services are up)
```

**Expected:** 6 containers start: `aistack-ollama`, `aistack-open-webui`, `aistack-comfyui`, `aistack-watchtower`, `aistack-grafana`, `aistack-vram-manager`.

---

## Step 3: Verify All Services Running

```bash
docker compose -f docker-compose.dev.yaml ps
```

**Expected output (all healthy/running):**

| Name | Status | Ports |
|------|--------|-------|
| aistack-ollama | Running (healthy) | 11434 |
| aistack-open-webui | Running (healthy) | 3000→8080 |
| aistack-comfyui | Running (healthy) | 8188 |
| aistack-grafana | Running (healthy) | 3001→3000 |
| aistack-watchtower | Running | — |
| aistack-vram-manager | Running | — |

**If a service is unhealthy or restarting:**
```bash
docker logs <container-name>
```

---

## Step 4: Test Individual Services

### 4a. Ollama

```bash
# API responds
curl -s http://localhost:11434/api/tags | python3 -m json.tool

# Pull a test model
docker exec aistack-ollama ollama pull mistral

# Quick inference test
curl -s http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Say hello in one sentence.",
  "stream": false
}' | python3 -m json.tool
```

**Expected:** Model pulls successfully. Response contains generated text. Check `nvidia-smi` — Ollama should be using GPU memory.

### 4b. Open-WebUI

```bash
# Health endpoint
curl -s http://localhost:3000/health
```

Then open **http://localhost:3000** in a browser. Create an account, select the `mistral` model, send a message.

**Expected:** Chat interface loads. Messages get responses from Ollama.

### 4c. ComfyUI

```bash
# System stats endpoint
curl -s http://localhost:8188/system_stats | python3 -m json.tool
```

Then open **http://localhost:8188** in a browser. Load the default workflow and queue a generation (if a model is available).

**Expected:** ComfyUI UI loads. System stats show GPU info.

### 4d. Grafana

Open **http://localhost:3001** in a browser. Login with `admin` / `admin`.

**Expected:** Grafana dashboard loads. No data sources configured yet (expected for dev).

---

## Step 5: Test VRAM Manager

### 5a. Verify it's running and connected

```bash
docker logs aistack-vram-manager
```

**Expected output should include:**
```
VRAM Manager Started
Ollama URL: http://aistack-ollama:11434
ComfyUI URL: http://aistack-comfyui:8188
Check interval: 5s
VRAM threshold: 75%
✓ Both services are accessible
Monitoring started...
```

### 5b. Trigger a model load and watch the logs

Open two terminals side by side:

**Terminal 1 — VRAM Manager logs:**
```bash
docker logs -f aistack-vram-manager
```

**Terminal 2 — Trigger model load:**
```bash
# Pull a second model to trigger VRAM Manager
docker exec aistack-ollama ollama pull llama3.2

# Send a request to load it (triggers VRAM Manager)
curl -s http://localhost:11434/api/generate -d '{
  "model": "llama3.2",
  "prompt": "Hello",
  "stream": false
}' > /dev/null
```

**Expected in Terminal 1:**
```
New Ollama model(s) detected: {'llama3.2'}
✓ Freed ComfyUI memory (unload_models=False)
```

### 5c. Verify GPU memory after free

```bash
nvidia-smi
```

**Expected:** Ollama is using GPU memory for the new model. ComfyUI's GPU allocation should have dropped (if it had any loaded).

---

## Step 6: Test Under Load

### 6a. Concurrent chat + image generation

1. In **Open-WebUI** (browser): Start a conversation with `mistral`
2. In **ComfyUI** (browser): Queue an image generation workflow
3. Monitor in a terminal:
   ```bash
   watch -n 1 nvidia-smi
   ```

**Expected:** Both services run on GPU. VRAM Manager logs show activity if threshold is exceeded. No OOM errors.

### 6b. Check VRAM Manager handles pressure

```bash
# Watch VRAM Manager while both services are active
docker logs -f aistack-vram-manager
```

**Expected:** If VRAM exceeds 75%, you'll see threshold-triggered frees. If a new model loads, you'll see model-triggered frees.

---

## Step 7: Resource Check

```bash
# All container resource usage
docker stats --no-stream

# VRAM Manager specifically (should be <128MB RAM, <0.25 CPU)
docker stats aistack-vram-manager --no-stream
```

**Expected:** VRAM Manager uses ~30-50 MB RAM, <1% CPU.

---

## Step 8: Shutdown Test

```bash
# Graceful shutdown
docker compose -f docker-compose.dev.yaml down

# Verify all containers stopped
docker ps

# Verify volumes persist
docker volume ls | grep aistack
```

**Expected:** All containers stop. Volumes remain (data preserved).

---

## Verdict Checklist

| # | Check | Pass? |
|---|-------|-------|
| 1 | All 6 containers start and become healthy | ☐ |
| 2 | Ollama serves chat responses on GPU | ☐ |
| 3 | Open-WebUI frontend loads and connects to Ollama | ☐ |
| 4 | ComfyUI UI loads and shows GPU stats | ☐ |
| 5 | Grafana login works | ☐ |
| 6 | VRAM Manager connects to both services on startup | ☐ |
| 7 | VRAM Manager detects new model load and frees ComfyUI memory | ☐ |
| 8 | Concurrent chat + image generation works without OOM | ☐ |
| 9 | VRAM Manager resource usage is within limits (<128MB, <0.25 CPU) | ☐ |
| 10 | Graceful shutdown works, volumes persist | ☐ |

**If all 10 pass: Dev stack is operational.** 🎉

---

## Troubleshooting Quick Reference

| Problem | Command | Fix |
|---------|---------|-----|
| Container won't start | `docker logs <name>` | Check error message |
| GPU not found | `nvidia-smi` | Install NVIDIA Container Toolkit |
| VRAM Manager can't connect | `docker network inspect ai-stack-network` | Verify all on same network |
| Ollama on CPU (very slow) | `docker logs aistack-ollama \| grep offload` | VRAM Manager should auto-fix |
| ComfyUI OOM | Set `COMFYUI_CLI_ARGS=--lowvram` in `.env.dev` | Restart stack |
| Model pull fails | `docker exec aistack-ollama ollama list` | Check disk space |
