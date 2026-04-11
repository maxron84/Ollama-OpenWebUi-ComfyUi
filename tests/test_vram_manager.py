#!/usr/bin/env python3
"""
Tests for VRAM Manager.

Usage:
    pytest tests/test_vram_manager.py -v
"""

import time
import pytest
from unittest.mock import Mock, patch, call

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from vram_manager import VRAMManager


@pytest.fixture
def mgr():
    """Fresh VRAMManager with debug logging."""
    return VRAMManager(
        ollama_url="http://ollama:11434",
        comfyui_url="http://comfyui:8188",
        check_interval=5,
        vram_threshold=75,
        debug=True,
    )


# ── Ollama API ───────────────────────────────────────────────


@patch("vram_manager.requests.get")
def test_check_ollama_status_ok(mock_get, mgr):
    mock_get.return_value = Mock(status_code=200, json=lambda: {"models": []})
    assert mgr.check_ollama_status() == {"models": []}
    mock_get.assert_called_once_with("http://ollama:11434/api/tags", timeout=5)


@patch("vram_manager.requests.get")
def test_check_ollama_status_http_error(mock_get, mgr):
    mock_get.return_value = Mock(status_code=500)
    assert mgr.check_ollama_status() is None


@patch("vram_manager.requests.get")
def test_check_ollama_status_network_error(mock_get, mgr):
    import requests as req
    mock_get.side_effect = req.exceptions.ConnectionError("refused")
    assert mgr.check_ollama_status() is None


@patch("vram_manager.requests.get")
def test_check_ollama_ps_ok(mock_get, mgr):
    payload = {"models": [{"name": "mistral"}, {"name": "llama2"}]}
    mock_get.return_value = Mock(status_code=200, json=lambda: payload)
    result = mgr.check_ollama_ps()
    assert len(result["models"]) == 2
    mock_get.assert_called_once_with("http://ollama:11434/api/ps", timeout=5)


@patch("vram_manager.requests.get")
def test_check_ollama_ps_failure(mock_get, mgr):
    mock_get.return_value = Mock(status_code=503)
    assert mgr.check_ollama_ps() is None


# ── ComfyUI API ──────────────────────────────────────────────


@patch("vram_manager.requests.get")
def test_check_comfyui_status_ok(mock_get, mgr):
    stats = {"system": {"vram_used": 5e9, "vram_total": 16e9}}
    mock_get.return_value = Mock(status_code=200, json=lambda: stats)
    assert mgr.check_comfyui_status() == stats


@patch("vram_manager.requests.get")
def test_check_comfyui_status_failure(mock_get, mgr):
    import requests as req
    mock_get.side_effect = req.exceptions.Timeout("timeout")
    assert mgr.check_comfyui_status() is None


@patch("vram_manager.requests.post")
def test_free_comfyui_memory_soft(mock_post, mgr):
    mock_post.return_value = Mock(status_code=200)
    assert mgr.free_comfyui_memory(unload_models=False) is True
    mock_post.assert_called_once_with(
        "http://comfyui:8188/free",
        json={"unload_models": False, "free_memory": True},
        timeout=10,
    )
    assert mgr.stats["comfyui_frees"] == 1
    assert mgr.last_comfyui_free > 0


@patch("vram_manager.requests.post")
def test_free_comfyui_memory_aggressive(mock_post, mgr):
    mock_post.return_value = Mock(status_code=200)
    assert mgr.free_comfyui_memory(unload_models=True) is True
    assert mock_post.call_args[1]["json"]["unload_models"] is True


@patch("vram_manager.requests.post")
def test_free_comfyui_memory_http_error(mock_post, mgr):
    mock_post.return_value = Mock(status_code=500)
    assert mgr.free_comfyui_memory() is False
    assert mgr.stats["comfyui_frees"] == 0


@patch("vram_manager.requests.post")
def test_free_comfyui_memory_network_error(mock_post, mgr):
    import requests as req
    mock_post.side_effect = req.exceptions.ConnectionError("refused")
    assert mgr.free_comfyui_memory() is False
    assert mgr.stats["errors"] == 1


# ── nvidia-smi ───────────────────────────────────────────────


@patch("subprocess.run")
def test_get_vram_usage_ok(mock_run, mgr):
    mock_run.return_value = Mock(returncode=0, stdout="12000, 16000")
    result = mgr.get_vram_usage()
    assert result == {"used_mb": 12000, "total_mb": 16000, "used_percent": 75.0}


@patch("subprocess.run")
def test_get_vram_usage_not_available(mock_run, mgr):
    mock_run.side_effect = FileNotFoundError("nvidia-smi not found")
    assert mgr.get_vram_usage() is None


@patch("subprocess.run")
def test_get_vram_usage_nonzero_exit(mock_run, mgr):
    mock_run.return_value = Mock(returncode=1, stdout="")
    assert mgr.get_vram_usage() is None


# ── Decision logic ───────────────────────────────────────────


def test_should_free_new_model(mgr):
    mgr.last_ollama_models = {"mistral"}
    assert mgr.should_free_comfyui({"mistral", "llama2"}, None) is True


def test_should_free_vram_above_threshold(mgr):
    mgr.last_ollama_models = {"mistral"}
    vram = {"used_percent": 80.0, "used_mb": 12800, "total_mb": 16000}
    assert mgr.should_free_comfyui({"mistral"}, vram) is True


def test_should_not_free_below_threshold(mgr):
    mgr.last_ollama_models = {"mistral"}
    vram = {"used_percent": 50.0, "used_mb": 8000, "total_mb": 16000}
    assert mgr.should_free_comfyui({"mistral"}, vram) is False


def test_should_not_free_at_exact_threshold(mgr):
    mgr.last_ollama_models = {"mistral"}
    vram = {"used_percent": 75.0, "used_mb": 12000, "total_mb": 16000}
    assert mgr.should_free_comfyui({"mistral"}, vram) is False


def test_should_not_free_empty_models_no_vram(mgr):
    mgr.last_ollama_models = set()
    assert mgr.should_free_comfyui(set(), None) is False


def test_should_free_first_model_ever(mgr):
    """First model loaded (from empty set) should trigger."""
    mgr.last_ollama_models = set()
    assert mgr.should_free_comfyui({"mistral"}, None) is True


# ── Two-stage freeing ────────────────────────────────────────


@patch("vram_manager.requests.post")
def test_two_stage_freeing(mock_post, mgr):
    mock_post.return_value = Mock(status_code=200)

    # Stage 1: soft free
    mgr.free_comfyui_memory(unload_models=False)
    assert mock_post.call_args_list[0] == call(
        "http://comfyui:8188/free",
        json={"unload_models": False, "free_memory": True},
        timeout=10,
    )

    # Stage 2: aggressive free
    mgr.free_comfyui_memory(unload_models=True)
    assert mock_post.call_args_list[1] == call(
        "http://comfyui:8188/free",
        json={"unload_models": True, "free_memory": True},
        timeout=10,
    )
    assert mgr.stats["comfyui_frees"] == 2


# ── Rate limiting ────────────────────────────────────────────


def test_rate_limit_window(mgr):
    """Within 30s of last free, the run loop should skip freeing."""
    mgr.last_comfyui_free = time.time()
    elapsed = time.time() - mgr.last_comfyui_free
    assert elapsed < 30  # confirms we're inside the rate-limit window


# ── print_stats ──────────────────────────────────────────────


def test_print_stats_runs(mgr):
    mgr.stats["comfyui_frees"] = 3
    mgr.stats["errors"] = 1
    # Should not raise
    mgr.print_stats()


# ── run() startup checks ────────────────────────────────────


@patch("vram_manager.requests.get")
def test_run_exits_if_ollama_down(mock_get, mgr):
    mock_get.return_value = Mock(status_code=500)
    with pytest.raises(SystemExit):
        mgr.run()


@patch("vram_manager.requests.get")
def test_run_exits_if_comfyui_down(mock_get, mgr):
    def side_effect(url, **kwargs):
        if "/api/tags" in url:
            return Mock(status_code=200, json=lambda: {"models": []})
        return Mock(status_code=500)  # ComfyUI fails

    mock_get.side_effect = side_effect
    with pytest.raises(SystemExit):
        mgr.run()


# ── Initialization ───────────────────────────────────────────


def test_url_trailing_slash_stripped():
    m = VRAMManager(ollama_url="http://host:1234/", comfyui_url="http://host:5678/")
    assert m.ollama_url == "http://host:1234"
    assert m.comfyui_url == "http://host:5678"


def test_defaults():
    m = VRAMManager()
    assert m.ollama_url == "http://localhost:11434"
    assert m.comfyui_url == "http://localhost:8188"
    assert m.check_interval == 5
    assert m.vram_threshold == 75
    assert m.last_ollama_models == set()
    assert m.last_comfyui_free == 0
    assert m.stats["comfyui_frees"] == 0
    assert m.stats["errors"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
