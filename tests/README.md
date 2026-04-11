# VRAM Manager Tests

Unit and integration tests for the VRAM Manager script.

## Test Coverage

| Class | Focus |
|-------|-------|
| `TestVRAMManager` | Unit tests — individual methods in isolation |
| `TestVRAMManagerIntegration` | Integration — multi-step workflows |
| `TestVRAMManagerEdgeCases` | Boundary conditions and edge cases |

## Requirements

```bash
pip install -r tests/requirements.txt
```

## Running Tests

```bash
# From project root
pytest tests/test_vram_manager.py -v

# With detailed output
pytest tests/test_vram_manager.py -v --tb=long

# Run specific test class
pytest tests/test_vram_manager.py::TestVRAMManager -v

# Run with coverage
pip install pytest-cov
pytest tests/test_vram_manager.py --cov=scripts --cov-report=html -v
```

## Notes

- Tests use `pytest-mock` and `unittest.mock` to mock HTTP requests, subprocess calls, and time functions
- The test file imports from `scripts/vram_manager.py` using `importlib` due to the module structure
- Tests do not require a running GPU, Ollama, or ComfyUI instance
