#!/usr/bin/env python3
"""
Dynamic VRAM Manager for Ollama and ComfyUI

This script monitors Ollama's activity and automatically frees ComfyUI's VRAM
when Ollama needs to load models, preventing Ollama from falling back to CPU mode.

Features:
- Monitors Ollama API for model loading requests
- Automatically calls ComfyUI's free memory API
- Configurable thresholds and intervals
- Logging for debugging and monitoring

Requirements:
- Python 3.8+
- requests library (pip install requests)

Usage:
  python3 vram-manager.py [options]

Options:
  --ollama-url URL       Ollama API URL (default: http://localhost:11434)
  --comfyui-url URL      ComfyUI API URL (default: http://localhost:8188)
  --check-interval SEC   Check interval in seconds (default: 5)
  --vram-threshold PCT   Free ComfyUI VRAM when threshold exceeded (default: 75)
  --debug                Enable debug logging
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from typing import Dict, Optional

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)


class VRAMManager:
    """Manages VRAM allocation between Ollama and ComfyUI"""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        comfyui_url: str = "http://localhost:8188",
        check_interval: int = 5,
        vram_threshold: int = 75,
        debug: bool = False,
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.comfyui_url = comfyui_url.rstrip("/")
        self.check_interval = check_interval
        self.vram_threshold = vram_threshold

        # Setup logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)

        # Track state
        self.last_ollama_models = set()
        self.last_comfyui_free = 0
        self.stats = {
            "started": datetime.now().isoformat(),
            "ollama_model_loads": 0,
            "comfyui_frees": 0,
            "errors": 0,
        }

    def check_ollama_status(self) -> Optional[Dict]:
        """Check Ollama's current status and loaded models"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.debug(f"Failed to check Ollama status: {e}")
        return None

    def check_ollama_ps(self) -> Optional[Dict]:
        """Check which models are currently loaded in Ollama"""
        try:
            response = requests.get(f"{self.ollama_url}/api/ps", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.logger.debug(f"Ollama PS response: {data}")
                return data
        except requests.exceptions.RequestException as e:
            self.logger.debug(f"Failed to check Ollama PS: {e}")
        return None

    def check_comfyui_status(self) -> Optional[Dict]:
        """Check ComfyUI's current status"""
        try:
            response = requests.get(f"{self.comfyui_url}/system_stats", timeout=5)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.debug(f"Failed to check ComfyUI status: {e}")
        return None

    def free_comfyui_memory(self, unload_models: bool = False) -> bool:
        """
        Free ComfyUI's VRAM by clearing cache and optionally unloading models

        Args:
            unload_models: If True, fully unload models (more aggressive)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Free memory cache
            response = requests.post(f"{self.comfyui_url}/free", json={"unload_models": unload_models, "free_memory": True}, timeout=10)
            
            if response.status_code == 200:
                self.logger.info(f"✓ Freed ComfyUI memory (unload_models={unload_models})")
                self.stats["comfyui_frees"] += 1
                self.last_comfyui_free = time.time()
                return True
            else:
                self.logger.warning(f"Failed to free ComfyUI memory: HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error freeing ComfyUI memory: {e}")
            self.stats["errors"] += 1
            return False

    def get_vram_usage(self) -> Optional[Dict]:
        """Get VRAM usage from nvidia-smi if available"""
        try:
            import subprocess

            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                used, total = map(int, result.stdout.strip().split(","))
                return {
                    "used_mb": used,
                    "total_mb": total,
                    "used_percent": (used / total) * 100,
                }
        except Exception as e:
            self.logger.debug(f"Could not get VRAM usage: {e}")

        return None

    def should_free_comfyui(self, current_models: set, vram_info: Optional[Dict]) -> bool:
        """
        Determine if ComfyUI memory should be freed

        Returns True if:
        1. New model is being loaded in Ollama, OR
        2. VRAM usage exceeds threshold
        """
        # Check if new models are being loaded
        new_models = current_models - self.last_ollama_models
        if new_models:
            self.logger.info(f"New Ollama model(s) detected: {new_models}")
            return True

        # Check VRAM threshold
        if vram_info and vram_info["used_percent"] > self.vram_threshold:
            self.logger.info(
                f"VRAM usage at {vram_info['used_percent']:.1f}% "
                f"(threshold: {self.vram_threshold}%)"
            )
            return True

        return False

    def run(self):
        """Main monitoring loop"""
        self.logger.info("=" * 60)
        self.logger.info("VRAM Manager Started")
        self.logger.info(f"Ollama URL: {self.ollama_url}")
        self.logger.info(f"ComfyUI URL: {self.comfyui_url}")
        self.logger.info(f"Check interval: {self.check_interval}s")
        self.logger.info(f"VRAM threshold: {self.vram_threshold}%")
        self.logger.info("=" * 60)

        # Verify services are accessible
        if not self.check_ollama_status():
            self.logger.error("Cannot connect to Ollama. Ensure it's running.")
            sys.exit(1)

        if not self.check_comfyui_status():
            self.logger.error("Cannot connect to ComfyUI. Ensure it's running.")
            sys.exit(1)

        self.logger.info("✓ Both services are accessible")
        self.logger.info("Monitoring started...")

        try:
            while True:
                # Get current state
                ollama_ps = self.check_ollama_ps()
                vram_info = self.get_vram_usage()

                # Extract currently loaded models
                current_models = set()
                if ollama_ps and "models" in ollama_ps:
                    for model in ollama_ps["models"]:
                        if "name" in model:
                            current_models.add(model["name"])

                # Log current state (debug)
                if current_models:
                    self.logger.debug(f"Loaded models: {current_models}")
                if vram_info:
                    self.logger.debug(
                        f"VRAM: {vram_info['used_mb']}MB / {vram_info['total_mb']}MB "
                        f"({vram_info['used_percent']:.1f}%)"
                    )

                # Check if we should free ComfyUI memory
                if self.should_free_comfyui(current_models, vram_info):
                    # Don't free too frequently (minimum 30 seconds between frees)
                    time_since_last_free = time.time() - self.last_comfyui_free
                    if time_since_last_free > 30:
                        # First try soft free (cache only)
                        if self.free_comfyui_memory(unload_models=False):
                            # If VRAM is still very high, do aggressive free
                            time.sleep(2)  # Give it a moment
                            new_vram = self.get_vram_usage()
                            if new_vram and new_vram["used_percent"] > 85:
                                self.logger.info("VRAM still high, performing aggressive free...")
                                self.free_comfyui_memory(unload_models=True)
                    else:
                        self.logger.debug(
                            f"Skipping free (last free was {time_since_last_free:.0f}s ago)"
                        )

                # Update tracking
                self.last_ollama_models = current_models

                # Sleep until next check
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            self.logger.info("\nShutdown requested...")
            self.print_stats()
            sys.exit(0)

    def print_stats(self):
        """Print statistics"""
        uptime = (datetime.now() - datetime.fromisoformat(self.stats["started"])).total_seconds()
        self.logger.info("=" * 60)
        self.logger.info("Statistics:")
        self.logger.info(f"  Uptime: {uptime / 3600:.1f} hours")
        self.logger.info(f"  Ollama model loads detected: {self.stats['ollama_model_loads']}")
        self.logger.info(f"  ComfyUI memory frees: {self.stats['comfyui_frees']}")
        self.logger.info(f"  Errors: {self.stats['errors']}")
        self.logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Dynamic VRAM Manager for Ollama and ComfyUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama API URL (default: http://localhost:11434)",
    )

    parser.add_argument(
        "--comfyui-url",
        default="http://localhost:8188",
        help="ComfyUI API URL (default: http://localhost:8188)",
    )

    parser.add_argument(
        "--check-interval",
        type=int,
        default=5,
        help="Check interval in seconds (default: 5)",
    )

    parser.add_argument(
        "--vram-threshold",
        type=int,
        default=75,
        help="Free ComfyUI VRAM when usage exceeds this percentage (default: 75)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.check_interval < 1:
        parser.error("Check interval must be at least 1 second")
    if not 0 <= args.vram_threshold <= 100:
        parser.error("VRAM threshold must be between 0 and 100")

    # Create and run manager
    manager = VRAMManager(
        ollama_url=args.ollama_url,
        comfyui_url=args.comfyui_url,
        check_interval=args.check_interval,
        vram_threshold=args.vram_threshold,
        debug=args.debug,
    )

    manager.run()


if __name__ == "__main__":
    main()

import json
import time
from pathlib import Path

STATE_FILE = Path("/shared/state/gpu_status.json")

def update_state(available: bool, holder: str):
    """Update shared GPU state file atomically with availability info."""
    state = {
        "gpu_available": available,
        "holder": holder,
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")

def wait_for_gpu(timeout: int = 60):
    """Wait until GPU becomes available or timeout expires."""
    if not STATE_FILE.exists():
        return True
    for _ in range(timeout):
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if state.get("gpu_available", True):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False
