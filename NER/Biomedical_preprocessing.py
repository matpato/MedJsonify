"""
This module provides a specialized text preprocessor for biomedical documents.
It aims to standardize and clean biomedical text by:
  1. Correcting common encoding issues in medical texts
  2. Expanding domain-specific abbreviations to their full forms
  3. Standardizing drug name spellings to canonical forms
  4. Removing domain-specific stopwords
  5. Normalizing punctuation and whitespace
  6. Providing batch processing capabilities for JSON files and directories
The preprocessor is designed to improve text quality for downstream NLP tasks
such as information extraction, entity recognition, and text classification
in biomedical applications.
"""

import os
import re
import json
import string
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# Download required NLTK resources
nltk.download('punkt_tab')
nltk.download('stopwords')

class BiomedicalPreprocessor:
    """
    A specialized text preprocessor for biomedical documents that handles
    common issues in medical text such as abbreviations, spelling variations,
    and domain-specific stopwords.
    """
    def __init__(self, preserve_case=False, keep_punctuation=True, remove_stops=True):
        """
        Initialize the preprocessor with customizable options.
        
        Args:
            preserve_case (bool): Whether to maintain the original text case
            keep_punctuation (bool): Whether to keep and standardize punctuation
            remove_stops (bool): Whether to remove stopwords
        """
        self.preserve_case = preserve_case
        self.keep_punctuation = keep_punctuation
        self.remove_stops = remove_stops
        
        # Dictionary of common biomedical abbreviations and their expanded forms
        self.bio_abbreviations = {
            "AD": "Alzheimer's disease",
            "MI": "myocardial infarction",
            "HTN": "hypertension",
            "DM": "diabetes mellitus",
            "CHF": "congestive heart failure",
            "COPD": "chronic obstructive pulmonary disease",
            "RA": "rheumatoid arthritis",
            "MS": "multiple sclerosis",
            "ASMD": "ASM-deficient Niemann-Pick disease",
        }
        
        # Dictionary of common drug name spelling variations
        self.drug_spelling_corrections = {
            "acetaminophen": ["acetaminophen", "acetaminophine", "acetaminofin"],
            "ibuprofen": ["ibuprofen", "ibuprofin", "ibuprophen"],
            "amoxicillin": ["amoxicillin", "amoxicilin", "amoxicillan"],
        }
        
        # Create a reverse mapping for quick lookup of misspelled drug names
        self.drug_spelling_map = {v: k for k, lst in self.drug_spelling_corrections.items() for v in lst if v != k}
        
        # Domain-specific stopwords common in medical literature
        self.custom_stopwords = [
            "Warnings", "Precautions", "Use", "Specific", "Populations", "see", "contraindications", "indications",
            "dosage", "administration", "adverse", "reactions", "drug", "interactions", "clinical", "studies"
        ]

    def fix_encoding_issues(self, text):
        """
        Fix common encoding issues found in biomedical texts, especially
        those extracted from PDFs or legacy systems.
        
        Args:
            text (str): The text to process
            
        Returns:
            str: Text with encoding issues fixed
        """
        replacements = {
            '\x92': "'", '\x93': '"', '\x94': '"',  # Smart quotes and apostrophes
            '\x96': '-', '\x97': '-', '\xa0': ' ',  # En/em dashes and non-breaking spaces
            '&amp;': '&', '&lt;': '<', '&gt;': '>'  # HTML entities
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def standardize_punctuation(self, text):
        """
        Standardize punctuation by adding spaces around them for better tokenization,
        or remove punctuation entirely based on initialization settings.
        
        Args:
            text (str): The text to process
            
        Returns:
            str: Text with standardized punctuation
        """
        if self.keep_punctuation:
            # Normalize multiple dashes to single dash
            text = re.sub(r'-+', '-', text)
            
            # Add spaces around punctuation for better tokenization
            for punct in [',', '.', ';', ':', '!', '?']:
                text = re.sub(f'(?<![A-Za-z0-9]){re.escape(punct)}', f' {punct} ', text)
            
            # Handle parentheses
            text = re.sub(r'\(', ' ( ', text)
            text = re.sub(r'\)', ' ) ', text)
            
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
        else:
            # Remove all punctuation if keep_punctuation is False
            text = text.translate(str.maketrans('', '', string.punctuation))
        return text.strip()

    def normalize_case(self, text):
        """
        Normalize text case based on initialization settings.
        
        Args:
            text (str): The text to process
            
        Returns:
            str: Text with normalized case
        """
        return text if self.preserve_case else text.lower()

    def correct_abbreviations(self, text):
        """
        Replace common biomedical abbreviations with their full forms.
        
        Args:
            text (str): The text to process
            
        Returns:
            str: Text with expanded abbreviations
        """
        for abbr, full in self.bio_abbreviations.items():
            text = re.sub(rf"\b{abbr}\b", full, text, flags=re.IGNORECASE)
        return text

    def correct_spelling(self, text):
        """
        Correct common misspellings of drug names using the predefined mapping.
        
        Args:
            text (str): The text to process
            
        Returns:
            str: Text with corrected drug name spellings
        """
        words = word_tokenize(text)
        corrected = [self.drug_spelling_map.get(w.lower(), w) for w in words]
        return ' '.join(corrected)

    def remove_stopwords(self, text):
        """
        Remove both standard English stopwords and domain-specific
        stopwords from the text.
        
        Args:
            text (str): The text to process
            
        Returns:
            str: Text with stopwords removed
        """
        # Get standard English stopwords from NLTK
        standard_stopwords = set(stopwords.words('english'))
        
        # Tokenize the text
        tokens = word_tokenize(text)
        
        # Remove standard stopwords
        filtered_tokens = [token for token in tokens if token.lower() not in standard_stopwords]
        
        # Remove custom biomedical stopwords
        custom_stopwords = set(word.lower() for word in self.custom_stopwords)
        filtered_tokens = [token for token in filtered_tokens if token.lower() not in custom_stopwords]
        
        return ' '.join(filtered_tokens)

    def preprocess_text(self, text):
        """
        Apply the complete preprocessing pipeline to a text string.
        
        Args:
            text (str): The text to process
            
        Returns:
            str: Fully preprocessed text
        """
        text = self.fix_encoding_issues(text)
        text = self.normalize_case(text)
        text = self.standardize_punctuation(text)
        text = self.correct_abbreviations(text)
        text = self.correct_spelling(text)
        if self.remove_stops:
            text = self.remove_stopwords(text)
        return text

    def preprocess_json_file(self, input_file, output_file, fields_to_process=None):
        """
        Preprocess text fields in a JSON file.
        
        Args:
            input_file (str): Path to the input JSON file
            output_file (str): Path to save the processed JSON file
            fields_to_process (list, optional): List of specific fields to process.
                                               If None, processes all string fields.
        """
        # Load JSON data
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if fields_to_process:
            # Process only specified fields
            for field in fields_to_process:
                if field in data and isinstance(data[field], str):
                    # Preserve original text in a new field
                    data[f"{field}_original"] = data[field]
                    # Replace field with processed text
                    data[field] = self.preprocess_text(data[field])
        else:
            # Process all string fields
            for key, value in data.items():
                if isinstance(value, str):
                    data[key] = self.preprocess_text(value)
        
        # Save processed data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def preprocess_directory(self, input_dir, output_dir, fields_to_process=None):
        """
        Preprocess all JSON files in a directory.
        
        Args:
            input_dir (str): Directory containing input JSON files
            output_dir (str): Directory to save processed JSON files
            fields_to_process (list, optional): List of specific fields to process
                                               in each JSON file
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Process each JSON file in the input directory
        for filename in os.listdir(input_dir):
            if filename.endswith(".json"):
                input_file = os.path.join(input_dir, filename)
                output_file = os.path.join(output_dir, filename)
                self.preprocess_json_file(input_file, output_file, fields_to_process)

