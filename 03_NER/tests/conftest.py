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