# Smoke Test Plan

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

## Step 1: Verify ComfyUI Image is Pullable

```bash
docker pull yanwk/comfyui-boot:cu128-slim
```

**Expected:** Pull succeeds. Image is ~several GB; allow a few minutes on first pull.

---

## Step 2: Configure and Start the Stack

```bash
# Copy and edit the env file
cp .env.example .env
# Set WEBUI_SECRET_KEY — required, stack will not start without it:
#   openssl rand -hex 32

# Pull all images first (so startup is clean)
docker compose pull

# Start all services
docker compose up -d

# Watch startup progress (Ctrl+C to stop following)
docker compose logs -f
```

**Expected:** 4 containers start: `aistack-ollama`, `aistack-open-webui`, `aistack-comfyui`, `aistack-vram-manager`.

---

## Step 3: Verify All Services Running

```bash
docker compose ps
```

**Expected output (all healthy/running):**

| Name | Status | Ports |
|------|--------|-------|
| aistack-ollama | Running (healthy) | 11434 |
| aistack-open-webui | Running (healthy) | 3000→8080 |
| aistack-comfyui | Running (healthy) | 8188 |
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
curl -s http://localhost:3000/health
```

Then open **http://localhost:3000** in a browser. Create an account, select the `mistral` model, send a message.

**Expected:** Chat interface loads. Messages get responses from Ollama.

### 4c. ComfyUI

```bash
curl -s http://localhost:8188/system_stats | python3 -m json.tool
```

Then open **http://localhost:8188** in a browser. Load the default workflow and queue a generation (if a model is available).

**Expected:** ComfyUI UI loads. System stats show GPU info.

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

**Terminal 1 — VRAM Manager logs:**
```bash
docker logs -f aistack-vram-manager
```

**Terminal 2 — Trigger model load:**
```bash
docker exec aistack-ollama ollama pull llama3.2

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

**Expected:** Ollama is using GPU memory for the new model. ComfyUI's GPU allocation should have dropped.

---

## Step 6: Test Under Load

1. In **Open-WebUI** (browser): Start a conversation with `mistral`
2. In **ComfyUI** (browser): Queue an image generation workflow
3. Monitor:
   ```bash
   watch -n 1 nvidia-smi
   docker logs -f aistack-vram-manager
   ```

**Expected:** Both services run on GPU. No OOM errors. VRAM Manager logs show frees if threshold is exceeded.

---

## Step 7: Resource Check

```bash
docker stats --no-stream
docker stats aistack-vram-manager --no-stream
```

**Expected:** VRAM Manager uses ~30–50 MB RAM, <1% CPU.

---

## Step 8: Shutdown Test

```bash
docker compose down
docker ps
docker volume ls | grep aistack
```

**Expected:** All containers stop. Volumes remain (data preserved).

---

## Verdict Checklist

| # | Check | Pass? |
|---|-------|-------|
| 1 | All 4 containers start and become healthy | ☐ |
| 2 | Ollama serves chat responses on GPU | ☐ |
| 3 | Open-WebUI frontend loads and connects to Ollama | ☐ |
| 4 | ComfyUI UI loads and shows GPU stats | ☐ |
| 5 | VRAM Manager connects to both services on startup | ☐ |
| 6 | VRAM Manager detects new model load and frees ComfyUI memory | ☐ |
| 7 | Concurrent chat + image generation works without OOM | ☐ |
| 8 | VRAM Manager resource usage is within limits (<128MB, <0.25 CPU) | ☐ |
| 9 | Graceful shutdown works, volumes persist | ☐ |

**If all 9 pass: Stack is operational.**

---

## Troubleshooting Quick Reference

| Problem | Command | Fix |
|---------|---------|-----|
| Container won't start | `docker logs <name>` | Check error message |
| GPU not found | `nvidia-smi` | Install NVIDIA Container Toolkit |
| Stack won't start (WEBUI_SECRET_KEY) | — | Run `openssl rand -hex 32` and set in `.env` |
| VRAM Manager can't connect | `docker network inspect ai-stack-network` | Verify all on same network |
| Ollama on CPU (very slow) | `docker logs aistack-ollama \| grep offload` | VRAM Manager should auto-fix |
| ComfyUI OOM | Set `COMFYUI_CLI_ARGS=--lowvram` in `.env` | Restart stack |
| Model pull fails | `docker exec aistack-ollama ollama list` | Check disk space |
