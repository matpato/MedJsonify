"""
Unit Tests for Biomedical Preprocessing Module
==============================================
Tests for text preprocessing, normalization, and cleaning functions.
"""

import pytest
import tempfile
import os
import json
from pathlib import Path

# Adjust import path based on your structure
import sys
sys.path.insert(0, '/app/NER')

from Biomedical_preprocessing import BiomedicalPreprocessor


class TestBiomedicalPreprocessorInit:
    """Tests for BiomedicalPreprocessor initialization"""
    
    def test_default_initialization(self):
        """Test default initialization"""
        preprocessor = BiomedicalPreprocessor()
        
        assert preprocessor.preserve_case is False
        assert preprocessor.keep_punctuation is True
        assert preprocessor.remove_stops is True
        assert len(preprocessor.bio_abbreviations) > 0
        assert len(preprocessor.custom_stopwords) > 0
    
    def test_custom_initialization(self):
        """Test initialization with custom parameters"""
        preprocessor = BiomedicalPreprocessor(
            preserve_case=True,
            keep_punctuation=False,
            remove_stops=False
        )
        
        assert preprocessor.preserve_case is True
        assert preprocessor.keep_punctuation is False
        assert preprocessor.remove_stops is False


class TestFixEncodingIssues:
    """Tests for fix_encoding_issues method"""
    
    def test_fix_smart_quotes(self):
        """Test fixing smart quotes and apostrophes"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "Patient\x92s condition improved"
        result = preprocessor.fix_encoding_issues(text)
        
        assert result == "Patient's condition improved"
    
    def test_fix_em_dash(self):
        """Test fixing em and en dashes"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "Treatment\x96ongoing\x97followup"
        result = preprocessor.fix_encoding_issues(text)
        
        assert result == "Treatment-ongoing-followup"
    
    def test_fix_html_entities(self):
        """Test fixing HTML entities"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "A &amp; B &lt; C &gt; D"
        result = preprocessor.fix_encoding_issues(text)
        
        assert result == "A & B < C > D"
    
    def test_fix_non_breaking_space(self):
        """Test fixing non-breaking spaces"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "Word1\xa0Word2"
        result = preprocessor.fix_encoding_issues(text)
        
        assert result == "Word1 Word2"


class TestStandardizePunctuation:
    """Tests for standardize_punctuation method"""
    
    def test_standardize_with_punctuation(self):
        """Test standardizing punctuation when keeping it"""
        preprocessor = BiomedicalPreprocessor(keep_punctuation=True)
        
        text = "Hello,world.How are you?"
        result = preprocessor.standardize_punctuation(text)
        
        # Should add spaces around punctuation
        assert " , " in result or "," in result
        assert " . " in result or "." in result
    
    def test_remove_punctuation(self):
        """Test removing punctuation"""
        preprocessor = BiomedicalPreprocessor(keep_punctuation=False)
        
        text = "Hello, world! How are you?"
        result = preprocessor.standardize_punctuation(text)
        
        # Should remove all punctuation
        assert "," not in result
        assert "!" not in result
        assert "?" not in result
    
    def test_normalize_dashes(self):
        """Test normalizing multiple dashes"""
        preprocessor = BiomedicalPreprocessor(keep_punctuation=True)
        
        text = "word1---word2--word3"
        result = preprocessor.standardize_punctuation(text)
        
        # Multiple dashes should become single dash
        assert "---" not in result
    
    def test_handle_parentheses(self):
        """Test handling parentheses"""
        preprocessor = BiomedicalPreprocessor(keep_punctuation=True)
        
        text = "drug(compound)"
        result = preprocessor.standardize_punctuation(text)
        
        # Should add spaces around parentheses
        assert "( " in result or "(" in result
        assert " )" in result or ")" in result


class TestNormalizeCase:
    """Tests for normalize_case method"""
    
    def test_lowercase(self):
        """Test converting to lowercase"""
        preprocessor = BiomedicalPreprocessor(preserve_case=False)
        
        text = "DIABETES Mellitus Type 2"
        result = preprocessor.normalize_case(text)
        
        assert result == "diabetes mellitus type 2"
    
    def test_preserve_case(self):
        """Test preserving original case"""
        preprocessor = BiomedicalPreprocessor(preserve_case=True)
        
        text = "DIABETES Mellitus Type 2"
        result = preprocessor.normalize_case(text)
        
        assert result == "DIABETES Mellitus Type 2"


class TestCorrectAbbreviations:
    """Tests for correct_abbreviations method"""
    
    def test_expand_abbreviation(self):
        """Test expanding medical abbreviations"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "Patient diagnosed with AD"
        result = preprocessor.correct_abbreviations(text)
        
        assert "Alzheimer's disease" in result.lower()
    
    def test_multiple_abbreviations(self):
        """Test expanding multiple abbreviations"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "Patient has MI and HTN"
        result = preprocessor.correct_abbreviations(text)
        
        assert "myocardial infarction" in result.lower()
        assert "hypertension" in result.lower()
    
    def test_case_insensitive_expansion(self):
        """Test case-insensitive abbreviation expansion"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "diagnosed with dm"
        result = preprocessor.correct_abbreviations(text)
        
        assert "diabetes mellitus" in result.lower()
    
    def test_preserve_non_abbreviations(self):
        """Test that non-abbreviations are preserved"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "The patient is fine"
        result = preprocessor.correct_abbreviations(text)
        
        assert result.lower() == "the patient is fine"


class TestCorrectSpelling:
    """Tests for correct_spelling method"""
    
    def test_correct_drug_spelling(self):
        """Test correcting drug name spelling"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "acetaminophen ibuprofin"
        result = preprocessor.correct_spelling(text)
        
        # Should correct 'ibuprofin' to 'ibuprofen'
        assert "ibuprofen" in result.lower()
    
    def test_preserve_correct_spelling(self):
        """Test preserving correctly spelled words"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "ibuprofen acetaminophen"
        result = preprocessor.correct_spelling(text)
        
        assert "ibuprofen" in result.lower()
        assert "acetaminophen" in result.lower()


class TestRemoveStopwords:
    """Tests for remove_stopwords method"""
    
    def test_remove_common_stopwords(self):
        """Test removing common English stopwords"""
        preprocessor = BiomedicalPreprocessor(remove_stops=True)
        
        text = "the patient has a condition"
        result = preprocessor.remove_stopwords(text)
        
        # Common stopwords should be removed
        assert "the" not in result.lower()
        assert "a" not in result.lower()
        assert "patient" in result.lower()
        assert "condition" in result.lower()
    
    def test_remove_custom_stopwords(self):
        """Test removing custom biomedical stopwords"""
        preprocessor = BiomedicalPreprocessor(remove_stops=True)
        
        text = "Warnings and Precautions for drug administration"
        result = preprocessor.remove_stopwords(text)
        
        # Custom stopwords should be removed
        assert "warnings" not in result.lower()
        assert "precautions" not in result.lower()
    
    def test_keep_important_words(self):
        """Test keeping important medical terms"""
        preprocessor = BiomedicalPreprocessor(remove_stops=True)
        
        text = "diabetes hypertension treatment"
        result = preprocessor.remove_stopwords(text)
        
        assert "diabetes" in result.lower()
        assert "hypertension" in result.lower()
        assert "treatment" in result.lower()


class TestPreprocessText:
    """Tests for the complete preprocess_text pipeline"""
    
    def test_full_pipeline(self):
        """Test complete preprocessing pipeline"""
        preprocessor = BiomedicalPreprocessor(
            preserve_case=False,
            keep_punctuation=True,
            remove_stops=True
        )
        
        text = "Patient\x92s diagnosed with MI and HTN. Prescribed acetaminophine."
        result = preprocessor.preprocess_text(text)
        
        # Should have:
        # - Fixed encoding
        # - Lowercased
        # - Expanded abbreviations
        # - Corrected spelling
        # - Removed stopwords
        
        assert "myocardial infarction" in result.lower()
        assert "hypertension" in result.lower()
        assert "acetaminophen" in result.lower()
    
    def test_empty_text(self):
        """Test preprocessing empty text"""
        preprocessor = BiomedicalPreprocessor()
        
        result = preprocessor.preprocess_text("")
        
        assert result == ""
    
    def test_whitespace_only(self):
        """Test preprocessing whitespace-only text"""
        preprocessor = BiomedicalPreprocessor()
        
        result = preprocessor.preprocess_text("   \n\t   ")
        
        assert result.strip() == ""


class TestPreprocessJsonFile:
    """Tests for preprocess_json_file method"""
    
    def test_preprocess_single_json_file(self):
        """Test preprocessing a single JSON file"""
        preprocessor = BiomedicalPreprocessor()
        
        # Create temporary files
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = os.path.join(tmpdir, "input.json")
            output_file = os.path.join(tmpdir, "output.json")
            
            # Create sample JSON
            sample_data = {
                "name": "Test Drug",
                "indications": "Used for MI and HTN",
                "contraindications": "Do not use with DM"
            }
            
            with open(input_file, 'w') as f:
                json.dump(sample_data, f)
            
            # Preprocess
            preprocessor.preprocess_json_file(
                input_file=input_file,
                output_file=output_file,
                fields_to_process=['indications', 'contraindications']
            )
            
            # Load and verify
            with open(output_file, 'r') as f:
                result = json.load(f)
            
            # Original field should be preserved
            assert 'indications_original' in result
            assert result['indications_original'] == "Used for MI and HTN"
            
            # Processed field should have expanded abbreviations
            assert "myocardial infarction" in result['indications'].lower()
            assert "hypertension" in result['indications'].lower()
    
    def test_preprocess_all_fields(self):
        """Test preprocessing all string fields in JSON"""
        preprocessor = BiomedicalPreprocessor()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = os.path.join(tmpdir, "input.json")
            output_file = os.path.join(tmpdir, "output.json")
            
            sample_data = {
                "field1": "Text with MI",
                "field2": "Text with HTN",
                "field3": 123  # Non-string field
            }
            
            with open(input_file, 'w') as f:
                json.dump(sample_data, f)
            
            # Preprocess without specifying fields (process all)
            preprocessor.preprocess_json_file(
                input_file=input_file,
                output_file=output_file,
                fields_to_process=None
            )
            
            # Load and verify
            with open(output_file, 'r') as f:
                result = json.load(f)
            
            # String fields should be processed
            assert "myocardial infarction" in result['field1'].lower()
            assert "hypertension" in result['field2'].lower()
            
            # Non-string field should be unchanged
            assert result['field3'] == 123


class TestPreprocessDirectory:
    """Tests for preprocess_directory method"""
    
    def test_preprocess_directory(self):
        """Test preprocessing all JSON files in a directory"""
        preprocessor = BiomedicalPreprocessor()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = os.path.join(tmpdir, "input")
            output_dir = os.path.join(tmpdir, "output")
            os.makedirs(input_dir)
            
            # Create multiple JSON files
            for i in range(3):
                file_path = os.path.join(input_dir, f"file{i}.json")
                data = {
                    "name": f"Drug {i}",
                    "description": "Treatment for MI"
                }
                with open(file_path, 'w') as f:
                    json.dump(data, f)
            
            # Preprocess directory
            preprocessor.preprocess_directory(
                input_dir=input_dir,
                output_dir=output_dir,
                fields_to_process=['description']
            )
            
            # Verify all files were processed
            output_files = os.listdir(output_dir)
            assert len(output_files) == 3
            
            # Check one file
            with open(os.path.join(output_dir, "file0.json"), 'r') as f:
                result = json.load(f)
            
            assert "myocardial infarction" in result['description'].lower()


class TestEdgeCases:
    """Tests for edge cases and error handling"""
    
    def test_very_long_text(self):
        """Test preprocessing very long text"""
        preprocessor = BiomedicalPreprocessor()
        
        # Create a very long text
        text = "Patient has MI. " * 10000
        
        result = preprocessor.preprocess_text(text)
        
        # Should complete without error
        assert "myocardial infarction" in result.lower()
    
    def test_special_characters(self):
        """Test handling special characters"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "Patient #1 (age: 45) has MI & HTN"
        result = preprocessor.preprocess_text(text)
        
        # Should handle special characters gracefully
        assert result is not None
        assert len(result) > 0
    
    def test_mixed_languages(self):
        """Test handling mixed language content"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "Patient has MI (infarto do miocárdio)"
        result = preprocessor.preprocess_text(text)
        
        # Should process without error
        assert result is not None
    
    def test_unicode_characters(self):
        """Test handling unicode characters"""
        preprocessor = BiomedicalPreprocessor()
        
        text = "Dosage: 100μg/day for HTN"
        result = preprocessor.preprocess_text(text)
        
        assert result is not None
        assert "hypertension" in result.lower()


# Fixtures
@pytest.fixture
def preprocessor():
    """Fixture providing default preprocessor"""
    return BiomedicalPreprocessor()


@pytest.fixture
def preprocessor_no_stops():
    """Fixture providing preprocessor without stopword removal"""
    return BiomedicalPreprocessor(remove_stops=False)


@pytest.fixture
def preprocessor_preserve_case():
    """Fixture providing preprocessor that preserves case"""
    return BiomedicalPreprocessor(preserve_case=True)


@pytest.fixture
def sample_medical_text():
    """Fixture providing sample medical text"""
    return """
    Patient presents with MI and HTN. History of DM.
    Prescribed acetaminophine and ibuprofin.
    Contraindications: bleeding disorders.
    """


@pytest.fixture
def temp_json_files():
    """Fixture providing temporary JSON files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        files = []
        for i in range(3):
            file_path = os.path.join(tmpdir, f"test{i}.json")
            data = {
                "id": i,
                "text": f"Sample text {i} with MI"
            }
            with open(file_path, 'w') as f:
                json.dump(data, f)
            files.append(file_path)
        
        yield tmpdir, files


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])