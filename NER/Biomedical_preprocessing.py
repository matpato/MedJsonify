# biomedical_preprocessing.py

import re
import json
import string
import html
import os
import nltk
from nltk.tokenize import word_tokenize
from bs4 import BeautifulSoup
from tqdm import tqdm

# Download required NLTK resources
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class BiomedicalPreprocessor:
    """
    A class for preprocessing text data from JSON files for biomedical NER tasks.
    """
    
    def __init__(self, preserve_case=True, keep_punctuation=True):
        """
        Initialize the preprocessor with configuration options.
        
        Args:
            preserve_case (bool): Whether to preserve the original case of text
            keep_punctuation (bool): Whether to keep punctuation that may be part of biomedical entities
        """
        self.preserve_case = preserve_case
        self.keep_punctuation = keep_punctuation
        
        # Common biomedical abbreviations and their expanded forms
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
            
            # Add more as needed
        }
        
        # Common misspellings of drug names
        self.drug_spelling_corrections = {
            "acetaminophen": ["acetaminophen", "acetaminophine", "acetaminofin"],
            "ibuprofen": ["ibuprofen", "ibuprofin", "ibuprophen"],
            "amoxicillin": ["amoxicillin", "amoxicilin", "amoxicillan"],
            # Add more as needed
        }
        
        # Create reverse mapping for drug spelling corrections
        self.drug_spelling_map = {}
        for correct, variants in self.drug_spelling_corrections.items():
            for variant in variants:
                if variant != correct:
                    self.drug_spelling_map[variant] = correct
    
    def remove_html_tags(self, text):
        """Remove HTML tags and decode HTML entities"""
        # Use BeautifulSoup to parse and remove HTML
        text = BeautifulSoup(text, "html.parser").get_text()
        # Decode HTML entities
        text = html.unescape(text)
        return text
    
    def standardize_whitespace(self, text):
        """Standardize whitespace to single spaces"""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def fix_encoding_issues(self, text):
        """Fix common encoding issues"""
        # Replace common problematic characters
        text = text.replace('\x92', "'")
        text = text.replace('\x93', '"')
        text = text.replace('\x94', '"')
        text = text.replace('\x96', '-')
        text = text.replace('\x97', '-')
        return text
    
    def standardize_punctuation(self, text):
        """Standardize punctuation without removing biomedically relevant markers"""
        if self.keep_punctuation:
            # Replace multiple dashes with single dash (but keep the dash)
            text = re.sub(r'-+', '-', text)
            # Ensure spaces around punctuation except for specific cases
            # Keep punctuation in patterns like "COVID-19", "5-HTP", "50mg"
            text = re.sub(r'(?<![A-Za-z0-9])([.,;:!?])', r' \1 ', text)
            # Standardize parentheses with spaces
            text = re.sub(r'\(', ' ( ', text)
            text = re.sub(r'\)', ' ) ', text)
            # Fix spaces
            text = re.sub(r'\s+', ' ', text)
        else:
            # Remove punctuation entirely (not recommended for NER)
            text = text.translate(str.maketrans('', '', string.punctuation))
        return text
    
    def normalize_case(self, text):
        """Normalize case if specified"""
        if not self.preserve_case:
            text = text.lower()
        return text
    
    def expand_abbreviations(self, text):
        """Expand common biomedical abbreviations"""
        # Create case-insensitive dictionary (all keys to lowercase)
        abbrev_lower = {k.lower(): v for k, v in text.items()}
        words = text.split()
        for i, word in enumerate(abbrev_lower):
            lower_word = word.lower()
            # Check if word is a known abbreviation (as a standalone word)
            if lower_word in self.bio_abbreviations:
                # Replace with the expanded form
                lower_word[i] = self.bio_abbreviations[lower_word]
        return ' '.join(lower_word)
    
    def correct_drug_spelling(self, text):
        """Correct common misspellings of drug names"""
        words = text.split()
        for i, word in enumerate(words):
            lower_word = word.lower()
            if lower_word in self.drug_spelling_map:
                # Replace with correct spelling but preserve case pattern
                if word.isupper():
                    words[i] = self.drug_spelling_map[lower_word].upper()
                elif word[0].isupper():
                    words[i] = self.drug_spelling_map[lower_word].capitalize()
                else:
                    words[i] = self.drug_spelling_map[lower_word]
        return ' '.join(words)
    
    def standardize_numbers_units(self, text):
        """Standardize formatting of numbers and units"""
        # Standardize spacing between numbers and units
        # e.g., "10mg" -> "10 mg", but keep "10mg" as one token for later NER
        text = re.sub(r'(\d+)([a-zA-Z]+)', r'\1 \2', text)
        
        # Standardize decimal points
        text = re.sub(r'(\d+),(\d+)', r'\1.\2', text)
        
        return text
    
    def add_custom_stopwords(self, custom_words):
        """
        Add custom stopwords to the stopwords list.
        
        Args:
            custom_words (list): List of custom stopwords to add
        """
        try:
            # Download stopwords if not already downloaded
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords')
        
        from nltk.corpus import stopwords
        
        # Get the default English stopwords
        self.stopwords = set(stopwords.words('english'))
        
        # Add custom stopwords
        if custom_words and isinstance(custom_words, list):
            self.stopwords.update(custom_words)
        
        return self.stopwords

    def remove_stopwords(self, text):
        """
        Remove stopwords from the text.
        
        Args:
            text (str): Input text
            
        Returns:
            str: Text with stopwords removed
        """
        if not hasattr(self, 'stopwords'):
            # Initialize stopwords if not already done
            self.add_custom_stopwords([])
        
        # Tokenize the text
        words = word_tokenize(text)
        
        # Remove stopwords
        filtered_words = [word for word in words if word.lower() not in self.stopwords]
        
        # Rejoin the words
        return ' '.join(filtered_words)
    
    def preprocess(self, text, remove_stopwords=False):
        """
        Apply all preprocessing steps to the input text
    
        Args:
            text (str): Input text
            remove_stopwords (bool): Whether to remove stopwords
            
        Returns:
            str: Preprocessed text
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Apply preprocessing steps in sequence
        text = self.remove_html_tags(text)
        text = self.fix_encoding_issues(text)
        text = self.standardize_whitespace(text)
        text = self.standardize_punctuation(text)
            
        text = self.expand_abbreviations(text)
        text = self.correct_drug_spelling(text)
        text = self.standardize_numbers_units(text)

        # Apply optional steps based on configuration
        if not self.preserve_case:
            text = self.normalize_case(text)

        # Remove stopwords if specified
        if remove_stopwords:
            text = self.remove_stopwords(text)
        
        return text
    
    def preprocess_json_file(self, input_file, output_file=None, text_fields=None, remove_stopwords=False):
        """
        Preprocess text fields in a JSON file.
        
        Args:
            input_file (str): Path to the input JSON file
            output_file (str, optional): Path to save the processed JSON file. 
                                        If None, will use input_file with '_preprocessed' suffix.
            text_fields (list, optional): List of field names containing text to preprocess.
                                        If None, will try to preprocess all string values.
            remove_stopwords (bool): Whether to remove stopwords during preprocessing
        
        Returns:
            dict: The preprocessed JSON data
        """
        print(f"Preprocessing JSON file: {input_file}")
        
        # Set default output file if not provided
        if output_file is None:
            file_name, file_ext = os.path.splitext(input_file)
            output_file = f"{file_name}_preprocessed{file_ext}"
        
        # Load JSON data
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Process the JSON data
        processed_data = self._process_json_object(data, text_fields, remove_stopwords)
        
        # Save processed data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, indent=2, ensure_ascii=False)
        
        print(f"Preprocessed data saved to: {output_file}")
        return processed_data
    
    def preprocess_json_directory(self, input_dir, output_dir=None, text_fields=None, file_pattern="*.json"):
        """
        Preprocess text fields in all JSON files in a directory.
        
        Args:
            input_dir (str): Path to the directory containing JSON files
            output_dir (str, optional): Path to save processed JSON files.
                                        If None, will use input_dir with '_processed' suffix.
            text_fields (list, optional): List of field names containing text to preprocess.
            file_pattern (str): Pattern to match JSON files
        
        Returns:
            int: Number of files processed
        """
        import glob
        
        # Set default output directory if not provided
        if output_dir is None:
            output_dir = f"{input_dir}_processed"
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get list of JSON files in the directory
        file_paths = glob.glob(os.path.join(input_dir, file_pattern))
        
        print(f"Found {len(file_paths)} JSON files in {input_dir}")
        
        # Process each file
        processed_count = 0
        for file_path in tqdm(file_paths, desc="Processing JSON files"):
            file_name = os.path.basename(file_path)
            output_file = os.path.join(output_dir, file_name)
            
            try:
                self.preprocess_json_file(file_path, output_file, text_fields)
                processed_count += 1
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
        
        print(f"Processed {processed_count} out of {len(file_paths)} files")
        return processed_count
    
    def _process_json_object(self, obj, text_fields=None, remove_stopwords=False):
        """
        Recursively process a JSON object, preprocessing text fields.
        
        Args:
            obj: JSON object (dict, list, or primitive value)
            text_fields (list, optional): List of field names to preprocess
            remove_stopwords (bool): Whether to remove stopwords
        
        Returns:
            The processed JSON object
        """
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if text_fields is None or key in text_fields:
                    if isinstance(value, str):
                        # Preprocess text field
                        result[key] = self.preprocess(value, remove_stopwords)
                        # Add original text field if value changed
                        if result[key] != value:
                            result[f"{key}_original"] = value
                    else:
                        # Recursively process non-string fields
                        result[key] = self._process_json_object(value, text_fields, remove_stopwords)
                else:
                    # Skip preprocessing for non-text fields
                    result[key] = self._process_json_object(value, text_fields, remove_stopwords)
            return result
        elif isinstance(obj, list):
            return [self._process_json_object(item, text_fields, remove_stopwords) for item in obj]
        else:
            # Return primitive values unchanged
            return obj


# Usage example
if __name__ == "__main__":
    # Initialize preprocessor with desired settings
    preprocessor = BiomedicalPreprocessor(preserve_case=True, keep_punctuation=True)
    
    # Example JSON data
    example_json = {
        "patient_id": "P12345",
        "demographics": {
            "age": 65,
            "gender": "male"
        },
        "medical_history": "Patient has a hx of HTN and DM type 2. Previously on 10mg Lipitor.",
        "current_medications": [
            {
                "name": "atorvastatin (Lipitor)",
                "dose": "20mg daily",
                "indication": "hypercholesterolemia"
            },
            {
                "name": "metformin",
                "dose": "500mg BID",
                "indication": "DM"
            }
        ],
        "notes": "Patient reported side-effects: mild muscle pain & occasional headaches."
    }
    
    # Save example to JSON file
    with open("example.json", "w") as f:
        json.dump(example_json, f, indent=2)
    
    # Add custom stopwords
    custom_stopwords = ["Warnings", "Precautions", "Use", "Specific", "Populations", 
                        "Indications", "Contraindications"]
    preprocessor.add_custom_stopwords(custom_stopwords)

    # Preprocess the JSON file
    # Only preprocess specific text fields
    text_fields = ["ingredients", "indications", "contraindications","warningsAndPrecautions",
                   "adverseReactions"]
    processed_json = preprocessor.preprocess_json_file("example.json", text_fields=text_fields)
    
    print("\nExample of processing a directory of JSON files:")
    print("preprocessor.preprocess_json_directory('/path/to/json_files', text_fields=['description', 'notes'])")

    
    
    # Process all JSON files in a directory

    # Add custom abbreviations and drug spelling corrections
    # Add custom abbreviations
    preprocessor.bio_abbreviations.update({
        "CAD": "coronary artery disease",
        "CKD": "chronic kidney disease",
        "PPI": "proton pump inhibitor"
    })

    # Add custom drug spelling corrections
    preprocessor.drug_spelling_corrections.update({
        "lisinopril": ["lisinopril", "lisenopril", "lysinopril"],
        "citalopram": ["citalopram", "citelopram", "citalopram"]
    })

    # Update the spelling map
    preprocessor.drug_spelling_map = {}
    for correct, variants in preprocessor.drug_spelling_corrections.items():
        for variant in variants:
            if variant != correct:
                preprocessor.drug_spelling_map[variant] = correct

    preprocessor.preprocess_json_directory(
    "data/patient_records/",
    output_dir="data/processed_records/",
    text_fields = ["ingredients", "indications", "contraindications","warningsAndPrecautions",
                   "adverseReactions"]
)