import os
import re
import json
import string
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

nltk.download('punkt_tab')
nltk.download('stopwords')

class BiomedicalPreprocessor:
    def __init__(self, preserve_case=False, keep_punctuation=True, remove_stops=True):
        self.preserve_case = preserve_case
        self.keep_punctuation = keep_punctuation
        self.remove_stops = remove_stops
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
        self.drug_spelling_corrections = {
            "acetaminophen": ["acetaminophen", "acetaminophine", "acetaminofin"],
            "ibuprofen": ["ibuprofen", "ibuprofin", "ibuprophen"],
            "amoxicillin": ["amoxicillin", "amoxicilin", "amoxicillan"],
        }
        self.drug_spelling_map = {v: k for k, lst in self.drug_spelling_corrections.items() for v in lst if v != k}
        self.custom_stopwords = [
            "Warnings", "Precautions", "Use", "Specific", "Populations", "see", "contraindications", "indications",
            "dosage", "administration", "adverse", "reactions", "drug", "interactions", "clinical", "studies"
        ]

    def fix_encoding_issues(self, text):
        replacements = {
            '\x92': "'", '\x93': '"', '\x94': '"',
            '\x96': '-', '\x97': '-', '\xa0': ' ',
            '&amp;': '&', '&lt;': '<', '&gt;': '>'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def standardize_punctuation(self, text):
        if self.keep_punctuation:
            text = re.sub(r'-+', '-', text)
            for punct in [',', '.', ';', ':', '!', '?']:
                text = re.sub(f'(?<![A-Za-z0-9]){re.escape(punct)}', f' {punct} ', text)
            text = re.sub(r'\(', ' ( ', text)
            text = re.sub(r'\)', ' ) ', text)
            text = re.sub(r'\s+', ' ', text)
        else:
            text = text.translate(str.maketrans('', '', string.punctuation))
        return text.strip()

    def normalize_case(self, text):
        return text if self.preserve_case else text.lower()

    def correct_abbreviations(self, text):
        for abbr, full in self.bio_abbreviations.items():
            text = re.sub(rf"\b{abbr}\b", full, text, flags=re.IGNORECASE)
        return text

    def correct_spelling(self, text):
        words = word_tokenize(text)
        corrected = [self.drug_spelling_map.get(w.lower(), w) for w in words]
        return ' '.join(corrected)

    def remove_stopwords(self, text):
        standard_stopwords = set(stopwords.words('english'))
        tokens = word_tokenize(text)
        filtered_tokens = [token for token in tokens if token.lower() not in standard_stopwords]
        custom_stopwords = set(word.lower() for word in self.custom_stopwords)
        filtered_tokens = [token for token in filtered_tokens if token.lower() not in custom_stopwords]
        return ' '.join(filtered_tokens)

    def preprocess_text(self, text):
        text = self.fix_encoding_issues(text)
        text = self.normalize_case(text)
        text = self.standardize_punctuation(text)
        text = self.correct_abbreviations(text)
        text = self.correct_spelling(text)
        if self.remove_stops:
            text = self.remove_stopwords(text)
        return text

    def preprocess_json_file(self, input_file, output_file, fields_to_process=None):
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if fields_to_process:
            for field in fields_to_process:
                if field in data and isinstance(data[field], str):
                    data[f"{field}_original"] = data[field]
                    data[field] = self.preprocess_text(data[field])
        else:
            for key, value in data.items():
                if isinstance(value, str):
                    data[key] = self.preprocess_text(value)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def preprocess_directory(self, input_dir, output_dir, fields_to_process=None):
        os.makedirs(output_dir, exist_ok=True)
        for filename in os.listdir(input_dir):
            if filename.endswith(".json"):
                input_file = os.path.join(input_dir, filename)
                output_file = os.path.join(output_dir, filename)
                self.preprocess_json_file(input_file, output_file, fields_to_process)

