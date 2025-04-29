import re
import json
import string
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# Download required NLTK resources
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')


class BiomedicalPreprocessor:
    bio_abbreviations = {
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

    drug_spelling_corrections = {
        "acetaminophen": ["acetaminophen", "acetaminophine", "acetaminofin"],
        "ibuprofen": ["ibuprofen", "ibuprofin", "ibuprophen"],
        "amoxicillin": ["amoxicillin", "amoxicilin", "amoxicillan"],
    }

    drug_spelling_map = {
        variant: correct
        for correct, variants in drug_spelling_corrections.items()
        for variant in variants if variant != correct
    }

    @staticmethod
    def fix_encoding_issues(text):
        replacements = {
            '\x92': "'", '\x93': '"', '\x94': '"',
            '\x96': '-', '\x97': '-', '\xa0': ' ',
            '&amp;': '&', '&lt;': '<', '&gt;': '>',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    @staticmethod
    def standardize_punctuation(text, keep_punctuation=True):
        if keep_punctuation:
            text = re.sub(r'-+', '-', text)
            for punct in [',', '.', ';', ':', '!', '?']:
                text = re.sub(f'(?<![A-Za-z0-9]){re.escape(punct)}', f' {punct} ', text)
            text = re.sub(r'\(', ' ( ', text)
            text = re.sub(r'\)', ' ) ', text)
            text = re.sub(r'\s+', ' ', text)
        else:
            text = text.translate(str.maketrans('', '', string.punctuation))
        return text.strip()

    @staticmethod
    def normalize_case(text, preserve_case=False):
        return text if preserve_case else text.lower()

    @classmethod
    def expand_abbreviations(cls, text):
        pattern = re.compile(r'\b(' + '|'.join(cls.bio_abbreviations.keys()) + r')\b', re.IGNORECASE)
        def replace(match):
            word = match.group(0)
            replacement = cls.bio_abbreviations.get(word.upper(), word)
            return replacement
        return pattern.sub(replace, text)

    @classmethod
    def correct_drug_spelling(cls, text):
        words = text.split()
        for i, word in enumerate(words):
            lower_word = word.lower()
            if lower_word in cls.drug_spelling_map:
                correct = cls.drug_spelling_map[lower_word]
                words[i] = correct.upper() if word.isupper() else \
                           correct.capitalize() if word[0].isupper() else correct
        return ' '.join(words)

    @staticmethod
    def remove_stopwords(text, standard_stopwords, custom_stopwords=None):
        tokens = word_tokenize(text)
        filtered = [t for t in tokens if t.lower() not in standard_stopwords]
        if custom_stopwords:
            custom_lower = [w.lower() for w in custom_stopwords]
            filtered = [t for t in filtered if t.lower() not in custom_lower]
        return ' '.join(filtered)

    @classmethod
    def preprocess_text(cls, text, preserve_case=False, keep_punctuation=True,
                        remove_stops=True, custom_stopwords=None):
        if not text or not isinstance(text, str):
            return ""

        text = cls.fix_encoding_issues(text)
        text = cls.standardize_punctuation(text, keep_punctuation)
        text = cls.normalize_case(text, preserve_case)
        text = cls.expand_abbreviations(text)
        text = cls.correct_drug_spelling(text)

        if remove_stops:
            standard_stopwords = set(stopwords.words('english'))
            text = cls.remove_stopwords(text, standard_stopwords, custom_stopwords)

        return re.sub(r'\s+', ' ', text).strip()

    @classmethod
    def process_json_object(cls, obj, preserve_case=False, keep_punctuation=True,
                            remove_stops=True, custom_stopwords=None):
        if isinstance(obj, dict):
            return {
                key: cls.process_json_object(value, preserve_case, keep_punctuation, remove_stops, custom_stopwords)
                if not isinstance(value, str) else
                {f"{key}_original": value, key: cls.preprocess_text(value, preserve_case, keep_punctuation, remove_stops, custom_stopwords)}
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [cls.process_json_object(item, preserve_case, keep_punctuation, remove_stops, custom_stopwords)
                    for item in obj]
        return obj

    @classmethod
    def process_json_file(cls, input_file_path, output_file_path, fields_to_process=None,
                          preserve_case=False, keep_punctuation=True, remove_stops=True):
        custom_stopwords = [
            "Warnings", "Precautions", "Use", "Specific", "Populations",
            "see", "contraindications", "indications", "dosage", "administration",
            "adverse", "reactions", "drug", "interactions", "clinical", "studies"
        ]

        with open(input_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if fields_to_process:
            for field in fields_to_process:
                if field in data and isinstance(data[field], str):
                    data[f"{field}_original"] = data[field]
                    data[field] = cls.preprocess_text(
                        data[field], preserve_case, keep_punctuation, remove_stops, custom_stopwords
                    )
        else:
            data = cls.process_json_object(data, preserve_case, keep_punctuation, remove_stops, custom_stopwords)

        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print(f"Processed JSON saved to {output_file_path}")
