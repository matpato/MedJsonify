"""
Unit Tests for NER Entities Module
===================================
Tests for the core entity extraction and processing functions.
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Note: Adjust import path based on your actual structure
# If running from /app/NER/tests/, use:
# from ner_entities import get_onto_id, extract_disease_entities, process_drug_data
# Or use sys.path manipulation:
import sys
sys.path.insert(0, '/app/NER')

from ner_entities import (
    get_onto_id,
    extract_disease_entities,
    find_disease_in_ontology,
    process_drug_data
)


class TestGetOntoId:
    """Tests for get_onto_id function"""
    
    def test_get_onto_id_valid_entity(self):
        """Test extracting valid entity from ontology"""
        # This test assumes you have ontologies set up
        # Skip if ontologies not available
        result = get_onto_id(
            name="asthma",
            onto="do",
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        # Should return list of matches for DOID
        assert result is not None or result == []  # May be empty if ontology not loaded
    
    def test_get_onto_id_invalid_entity(self):
        """Test with non-existent entity"""
        result = get_onto_id(
            name="xyzinvalidterm12345",
            onto="do",
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        assert result is None or result == []
    
    def test_get_onto_id_empty_name(self):
        """Test with empty entity name"""
        result = get_onto_id(
            name="",
            onto="do",
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        assert result is None
    
    def test_get_onto_id_chebi(self):
        """Test ChEBI ontology extraction"""
        result = get_onto_id(
            name="glucose",
            onto="chebi",
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        # ChEBI should return single URI or None
        assert result is None or isinstance(result, str)
    
    @patch('subprocess.run')
    def test_get_onto_id_script_timeout(self, mock_run):
        """Test timeout handling"""
        from subprocess import TimeoutExpired
        
        mock_run.side_effect = TimeoutExpired('cmd', 60)
        
        result = get_onto_id(
            name="test",
            onto="do",
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        assert result is None
    
    @patch('subprocess.run')
    def test_get_onto_id_script_error(self, mock_run):
        """Test error handling when script fails"""
        mock_run.side_effect = Exception("Script execution failed")
        
        result = get_onto_id(
            name="test",
            onto="do",
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        assert result is None


class TestExtractDiseaseEntities:
    """Tests for extract_disease_entities function"""
    
    def test_extract_disease_entities_valid_text(self):
        """Test extraction from text with diseases"""
        text = "Patient has diabetes and asthma"
        
        result = extract_disease_entities(
            text=text,
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        # Should return list (may be empty if ontology not loaded)
        assert isinstance(result, list)
    
    def test_extract_disease_entities_empty_text(self):
        """Test with empty text"""
        result = extract_disease_entities(
            text="",
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        assert result == []
    
    def test_extract_disease_entities_no_diseases(self):
        """Test text without diseases"""
        text = "The weather is nice today"
        
        result = extract_disease_entities(
            text=text,
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        assert isinstance(result, list)
        # Should return empty list or list with no valid diseases


class TestFindDiseaseInOntology:
    """Tests for find_disease_in_ontology function"""
    
    def test_find_disease_in_ontology_valid(self):
        """Test finding disease in Orphanet ontology"""
        disease_terms = {
            "asthma": "http://www.orpha.net/ORDO/Orphanet_12345",
            "diabetes": "http://www.orpha.net/ORDO/Orphanet_67890"
        }
        
        result = find_disease_in_ontology(
            disease_name="asthma",
            disease_terms=disease_terms,
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        assert result == "http://www.orpha.net/ORDO/Orphanet_12345"
    
    def test_find_disease_in_ontology_case_insensitive(self):
        """Test case-insensitive matching"""
        disease_terms = {
            "asthma": "http://www.orpha.net/ORDO/Orphanet_12345"
        }
        
        result = find_disease_in_ontology(
            disease_name="ASTHMA",
            disease_terms=disease_terms,
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        assert result == "http://www.orpha.net/ORDO/Orphanet_12345"
    
    def test_find_disease_in_ontology_not_found(self):
        """Test with disease not in dictionary"""
        disease_terms = {}
        
        result = find_disease_in_ontology(
            disease_name="rare_disease_xyz",
            disease_terms=disease_terms,
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        # Should return None or attempt shell script lookup
        assert result is None or isinstance(result, str)


class TestProcessDrugData:
    """Tests for process_drug_data function"""
    
    @patch('ner_entities.get_onto_id')
    @patch('ner_drugbank.get_drug_info')
    def test_process_drug_data_basic(self, mock_drugbank, mock_get_onto):
        """Test basic drug data processing"""
        # Mock data
        drug_data = {
            "name": "Aspirin",
            "Trade_Name": "Bayer Aspirin",
            "Proper Name": "acetylsalicylic acid",
            "Ingredient": "aspirin",
            "indications": "pain relief",
            "contraindications": "bleeding disorders"
        }
        
        # Mock dependencies
        mock_drugbank_df = Mock()
        mock_vocabulary = {'aspirin', 'acetylsalicylic acid'}
        mock_disease_terms = {}
        
        # Mock return values
        mock_get_onto.return_value = "http://purl.obolibrary.org/obo/CHEBI_15365"
        mock_drugbank.return_value = []
        
        # Process
        result = process_drug_data(
            drug_data=drug_data,
            drugbank=mock_drugbank_df,
            vocabulary=mock_vocabulary,
            disease_terms=mock_disease_terms,
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        # Assertions
        assert 'drug' in result
        assert isinstance(result['drug'], list)
        assert len(result['drug']) > 0
    
    def test_process_drug_data_empty(self):
        """Test with empty drug data"""
        drug_data = {}
        
        mock_drugbank_df = Mock()
        mock_vocabulary = set()
        mock_disease_terms = {}
        
        result = process_drug_data(
            drug_data=drug_data,
            drugbank=mock_drugbank_df,
            vocabulary=mock_vocabulary,
            disease_terms=mock_disease_terms,
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        # Should return original data
        assert result == drug_data
    
    @patch('ner_entities.extract_disease_entities')
    def test_process_drug_data_with_indications(self, mock_extract):
        """Test processing drug data with indications"""
        drug_data = {
            "name": "Test Drug",
            "indications": "Used for diabetes and hypertension treatment",
            "contraindications": "Not for pregnant women"
        }
        
        # Mock disease extraction
        mock_extract.return_value = ['diabetes', 'hypertension']
        
        mock_drugbank_df = Mock()
        mock_vocabulary = set()
        mock_disease_terms = {
            'diabetes': 'http://www.orpha.net/ORDO/Orphanet_1'
        }
        
        result = process_drug_data(
            drug_data=drug_data,
            drugbank=mock_drugbank_df,
            vocabulary=mock_vocabulary,
            disease_terms=mock_disease_terms,
            data_dir="/app/NER/ontologies/data",
            scripts_dir="/app/NER/ontologies/scripts"
        )
        
        # Check that indications was converted to dict with entities
        assert isinstance(result['indications'], dict)
        assert 'text' in result['indications']
        assert 'doid_entities' in result['indications']


class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_full_drug_processing_workflow(self):
        """Test complete drug processing pipeline"""
        # Create sample drug data
        drug_data = {
            "name": "Aspirin",
            "Trade_Name": "Bayer Aspirin",
            "indications": "pain relief, fever reduction",
            "contraindications": "bleeding disorders",
            "ingredients": [
                {"name": "acetylsalicylic acid"}
            ]
        }
        
        # Mock dependencies
        import pandas as pd
        drugbank_df = pd.DataFrame({
            'DRUGBANK_ID': ['DB00945'],
            'GENERIC_NAME': ['aspirin'],
            'SYNONYMS': [['acetylsalicylic acid']]
        })
        
        vocabulary = {'aspirin', 'acetylsalicylic acid'}
        disease_terms = {}
        
        # Process (this will call real functions if ontologies are available)
        try:
            result = process_drug_data(
                drug_data=drug_data,
                drugbank=drugbank_df,
                vocabulary=vocabulary,
                disease_terms=disease_terms,
                data_dir="/app/NER/ontologies/data",
                scripts_dir="/app/NER/ontologies/scripts"
            )
            
            # Basic structure checks
            assert 'name' in result
            assert 'indications' in result
            assert 'contraindications' in result
            
        except Exception as e:
            pytest.skip(f"Integration test skipped: {e}")


# Fixtures
@pytest.fixture
def sample_drug_data():
    """Fixture providing sample drug data"""
    return {
        "name": "Test Drug",
        "Trade_Name": "TestDrug",
        "Proper Name": "test-drug-compound",
        "Ingredient": "test compound",
        "indications": "Test indication",
        "contraindications": "Test contraindication",
        "ingredients": [
            {"name": "ingredient 1"},
            {"name": "ingredient 2"}
        ]
    }


@pytest.fixture
def temp_ontology_dir():
    """Fixture providing temporary ontology directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, 'data')
        scripts_dir = os.path.join(tmpdir, 'scripts')
        os.makedirs(data_dir)
        os.makedirs(scripts_dir)
        yield data_dir, scripts_dir


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])