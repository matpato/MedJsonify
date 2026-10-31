# MedJsonify NER - Test Suite

## Overview

This test suite provides comprehensive unit and integration tests for the MedJsonify NER (Named Entity Recognition) system.

## Test Files

1. **test_standalone_bioner.py** - Tests for the main NER class
   - Initialization and configuration
   - Ontology downloading and processing
   - Entity extraction
   - Metadata management

2. **test_ner_entities.py** - Tests for entity processing logic
   - Entity identification
   - Disease extraction
   - Drug data processing
   - Integration workflows

3. **test_preprocessing.py** - Tests for text preprocessing
   - Encoding fixes
   - Punctuation standardization
   - Abbreviation expansion
   - Stopword removal

## Prerequisites

### Install Test Dependencies

```bash
pip install pytest pytest-cov pytest-mock
```

Or add to your `requirements.txt`:
```
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
```

## Running Tests

### Run All Tests

```bash
# From the NER directory
cd /app/NER
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_standalone_bioner.py -v
pytest tests/test_ner_entities.py -v
pytest tests/test_preprocessing.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_standalone_bioner.py::TestStandaloneBioNERInit -v
```

### Run Specific Test Method

```bash
pytest tests/test_standalone_bioner.py::TestStandaloneBioNERInit::test_default_initialization -v
```

### Run with Coverage Report

```bash
pytest tests/ --cov=. --cov-report=html --cov-report=term
```

This will generate:
- Terminal coverage summary
- HTML report in `htmlcov/index.html`

### Run Tests in Docker

```bash
# Enter the Airflow container
docker exec -it airflow_webserver bash

# Navigate to NER directory
cd /app/NER

# Run tests
pytest tests/ -v
```

## Test Configuration

### Skip Tests Requiring Ontologies

Some tests require actual ontology files to be present. To skip these:

```bash
pytest tests/ -v -m "not requires_ontologies"
```

To mark tests that require ontologies, add this decorator:
```python
@pytest.mark.requires_ontologies
def test_something():
    # test code
```

### Run Only Fast Tests

```bash
pytest tests/ -v -m "not slow"
```

Mark slow tests with:
```python
@pytest.mark.slow
def test_something_slow():
    # test code
```

## Test Structure

```
NER/
├── tests/
│   ├── __init__.py
│   ├── test_standalone_bioner.py      # Main NER class tests
│   ├── test_ner_entities.py           # Entity processing tests
│   ├── test_preprocessing.py          # Text preprocessing tests
│   ├── conftest.py                    # Shared fixtures (create this)
│   └── README.md                      # This file
```

## Creating conftest.py (Shared Fixtures)

Create `/app/NER/tests/conftest.py`:

```python
"""
Shared test fixtures for NER test suite
"""
import pytest
import tempfile
import os
from pathlib import Path

@pytest.fixture(scope="session")
def test_data_dir():
    """Provide a temporary data directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture(scope="session")
def sample_ontology_data():
    """Provide sample ontology data"""
    return {
        'doid': {
            'url': 'http://purl.obolibrary.org/obo/doid.owl',
            'name': 'doid',
            'description': 'Disease Ontology'
        },
        'chebi': {
            'url': 'http://purl.obolibrary.org/obo/chebi/chebi_lite.owl',
            'name': 'chebi',
            'description': 'ChEBI Lite'
        }
    }

@pytest.fixture
def sample_drug_data():
    """Provide sample drug data for testing"""
    return {
        "name": "Test Drug",
        "Trade_Name": "TestDrug Brand",
        "Proper Name": "test-drug-compound",
        "Ingredient": "test compound",
        "indications": "Used for pain and fever",
        "contraindications": "Do not use if allergic",
        "ingredients": [
            {"name": "ingredient 1"},
            {"name": "ingredient 2"}
        ]
    }

# Add pytest markers
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requires_ontologies: mark test as requiring ontology files"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
```

## Continuous Integration

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Run Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        cd NER
        pytest tests/ -v --cov=. --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        file: ./coverage.xml
```

## Common Issues

### Issue: Import Errors

**Problem:** Tests can't import modules

**Solution:** Make sure to run tests from the correct directory and that `__init__.py` exists:

```bash
cd /app/NER
touch __init__.py
pytest tests/ -v
```

### Issue: Shell Scripts Not Found

**Problem:** Tests fail because shell scripts are missing

**Solution:** Ensure scripts exist and are executable:

```bash
chmod +x /app/NER/ontologies/scripts/*.sh
```

### Issue: Ontology Files Missing

**Problem:** Tests fail because ontology data files are missing

**Solution:** Either:
1. Skip tests requiring ontologies: `pytest -m "not requires_ontologies"`
2. Run setup to download ontologies: `python setup.py --all`

### Issue: Permission Errors

**Problem:** Tests fail with permission errors in Docker

**Solution:** Run tests as the correct user:

```bash
docker exec -u airflow -it airflow_webserver bash
cd /app/NER
pytest tests/ -v
```

## Debugging Tests

### Run with Verbose Output

```bash
pytest tests/ -vv
```

### Show Print Statements

```bash
pytest tests/ -v -s
```

### Stop on First Failure

```bash
pytest tests/ -v -x
```

### Run Last Failed Tests Only

```bash
pytest tests/ --lf
```

### Enter Debugger on Failure

```bash
pytest tests/ --pdb
```

## Writing New Tests

### Test Naming Convention

- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`

### Example Test

```python
import pytest

class TestMyFeature:
    """Tests for my feature"""
    
    def test_basic_functionality(self):
        """Test basic functionality"""
        result = my_function("input")
        assert result == "expected output"
    
    def test_edge_case(self):
        """Test edge case"""
        with pytest.raises(ValueError):
            my_function(None)
    
    @pytest.mark.slow
    def test_slow_operation(self):
        """Test that takes a long time"""
        # slow test code
        pass
```

## Test Coverage Goals

Target coverage by module:
- `standalone_bioner.py`: >80%
- `ner_entities.py`: >70%
- `Biomedical_preprocessing.py`: >85%
- `ner_drugbank.py`: >70%

Check current coverage:
```bash
pytest tests/ --cov=. --cov-report=term-missing
```

## Contributing Tests

When adding new features:
1. Write tests first (TDD approach)
2. Ensure tests pass locally
3. Check coverage doesn't decrease
4. Document any new test requirements

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Pytest Markers](https://docs.pytest.org/en/stable/mark.html)
- [Pytest Coverage](https://pytest-cov.readthedocs.io/)

## Support

For issues with tests, contact the development team or create an issue in the project repository.