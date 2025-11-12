# VRAM Manager Tests

Comprehensive unit and integration tests for the VRAM Manager script.

## Test Coverage

### Unit Tests (`TestVRAMManager`)
- ✅ Initialization and configuration
- ✅ Ollama API interactions (status, ps)
- ✅ ComfyUI API interactions (status, free memory)
- ✅ VRAM usage monitoring (nvidia-smi)
- ✅ Decision logic (should_free_comfyui)
- ✅ Error handling and recovery

### Integration Tests (`TestVRAMManagerIntegration`)
- ✅ Full monitoring cycle
- ✅ Rate limiting behavior
- ✅ Error recovery and retries
- ✅ Model change detection
- ✅ Multi-step workflows

### Edge Case Tests (`TestVRAMManagerEdgeCases`)
- ✅ Empty model lists
- ✅ Threshold boundary conditions
- ✅ Two-stage freeing strategy
- ✅ Statistics accumulation

## Requirements

```bash
pip install pytest pytest-mock requests
```

Or install from requirements file:
```bash
pip install -r tests/requirements.txt
```

## Running Tests

### Run All Tests

```bash
# From project root
pytest tests/test_vram_manager.py -v

# With detailed output
pytest tests/test_vram_manager.py -v --tb=long

# With debug logging
pytest tests/test_vram_manager.py -v --log-cli-level=DEBUG
```

### Run Specific Test Classes

```bash
# Unit tests only
pytest tests/test_vram_manager.py::TestVRAMManager -v

# Integration tests only
pytest tests/test_vram_manager.py::TestVRAMManagerIntegration -v

# Edge case tests only
pytest tests/test_vram_manager.py::TestVRAMManagerEdgeCases -v
```

### Run Specific Tests

```bash
# Single test
pytest tests/test_vram_manager.py::TestVRAMManager::test_initialization -v

# Multiple tests by keyword
pytest tests/test_vram_manager.py -k "ollama" -v
pytest tests/test_vram_manager.py -k "comfyui" -v
pytest tests/test_vram_manager.py -k "vram" -v
```

### Coverage Report

```bash
# Install coverage
pip install pytest-cov

# Run with coverage
pytest tests/test_vram_manager.py --cov=scripts --cov-report=html -v

# View coverage report
open htmlcov/index.html
```

## Test Structure

### Unit Tests
Tests individual components in isolation with mocked dependencies:
- API calls (requests)
- System commands (subprocess)
- Time-dependent behavior (time.sleep)

### Integration Tests
Tests multiple components working together:
- Full monitoring cycles
- API interactions sequence
- State management across operations

### Edge Cases
Tests boundary conditions and unusual scenarios:
- Empty/null values
- Threshold boundaries
- Race conditions
- Error scenarios

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install pytest pytest-mock requests
      - name: Run tests
        run: pytest tests/ -v
```

## Mocking Strategy

Tests use `pytest-mock` and `unittest.mock` to:
- **Mock HTTP requests** - Simulate Ollama/ComfyUI API responses
- **Mock subprocess** - Simulate nvidia-smi output
- **Mock time** - Control rate limiting behavior
- **Mock logging** - Verify log output

## Test Data

### Sample Ollama Responses

```python
# /api/ps response
{
    "models": [
        {"name": "mistral", "size": 4000000000},
        {"name": "llama2", "size": 7000000000}
    ]
}
```

### Sample ComfyUI Responses

```python
# /system_stats response
{
    "system": {
        "vram_used": 5000000000,
        "vram_total": 16000000000
    }
}
```

### Sample nvidia-smi Output

```
12000, 16000
```

## Troubleshooting

### Import Errors

If you get import errors:
```bash
# Make sure you're in the project root
cd /path/to/Ollama-OpenWebUi-ComfyUi

# Run tests from project root
pytest tests/test_vram_manager.py -v
```

### Module Not Found

```bash
# Ensure pytest can find the scripts directory
export PYTHONPATH=$PYTHONPATH:$(pwd)/scripts
pytest tests/test_vram_manager.py -v
```

### Mocking Issues

If mocks aren't working:
```bash
# Verify pytest-mock is installed
pip list | grep pytest-mock

# Reinstall if needed
pip install --upgrade pytest-mock
```

## Adding New Tests

### Template for Unit Test

```python
def test_new_feature(self, manager):
    """Test description"""
    # Arrange
    # ... setup test data
    
    # Act
    result = manager.new_method()
    
    # Assert
    assert result == expected_value
```

### Template for Integration Test

```python
@patch('requests.get')
@patch('requests.post')
def test_new_integration(self, mock_post, mock_get, manager):
    """Test description"""
    # Setup mocks
    mock_get.return_value = Mock(status_code=200)
    mock_post.return_value = Mock(status_code=200)
    
    # Execute workflow
    result = manager.workflow()
    
    # Verify interactions
    assert mock_get.called
    assert result is True
```

## Best Practices

1. **Isolation** - Each test should be independent
2. **Mocking** - Mock external dependencies (APIs, system calls)
3. **Assertions** - Test one thing per test
4. **Naming** - Use descriptive test names
5. **Setup** - Use fixtures for common setup
6. **Cleanup** - Tests should clean up after themselves

## Test Metrics

Expected test execution:
- **Total tests:** ~30
- **Execution time:** <5 seconds
- **Coverage target:** >80%

## Future Enhancements

- [ ] Performance benchmarks
- [ ] Load testing
- [ ] Stress testing
- [ ] Docker integration tests
- [ ] End-to-end tests with real services