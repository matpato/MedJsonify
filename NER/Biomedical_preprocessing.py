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

# Download required NLTK resources (only if not already available)
for _resource, _path in (('punkt_tab', 'tokenizers/punkt_tab'), ('stopwords', 'corpora/stopwords')):
    try:
        nltk.data.find(_path)
    except LookupError:
        nltk.download(_resource, quiet=True)

# Words that change the meaning of a statement ("not indicated"): never removed
# as stopwords (NLTK's English list contains them)
NEGATION_WORDS = {"no", "not", "nor", "never", "without", "n't", "against"}

# Statements in the Indications section that say what the drug is NOT for
# (e.g. "Limitations of Use: X is not indicated for ..."). Everything from the
# cue to the end of the sentence (or the next section marker) is removed before
# NER, so that the diseases mentioned there are not linked as indications.
NEGATED_INDICATION_CUES = re.compile(
    r"\blimitations? of use\b"
    r"|\bnot\s+(?:been\s+)?(?:indicated|established|approved|recommended|studied|shown|for\s+use)\b"
    r"|\bshould\s+not\s+be\s+used\b"
    r"|\bis\s+not\s+(?:effective|intended)\b",
    re.IGNORECASE)
# End of the removed part: end of sentence, or the next "( 1.2 )"-style marker
_STATEMENT_END = re.compile(r"\.(?=\s|$)|\(\s*\d+(?:\.\d+)*\s*\)")

# Population / risk context in the Indications section. In "prophylaxis of
# invasive Aspergillus infections in patients at high risk ... with prolonged
# neutropenia", the drug is for the infections; "neutropenia" only describes the
# patients and must not become an indication. Rule: after a therapeutic target
# ("treatment of X", "prophylaxis of X", "reduce the risk of X", ...) the text
# from a population cue ("in patients with", "in adults who", "at high risk of",
# "receiving", "undergoing") to the end of the statement is removed. If there is
# no target before the cue ("indicated in patients with type 2 diabetes"), or
# the population cue directly follows the target ("treatment of adult patients
# with multiple sclerosis"), nothing is removed: there, the disease in the
# population phrase IS the indication.
_TARGET_CUE = re.compile(
    r"\b(?:treatment|prophylaxis|prevention|management|control|relief|reduction)\s+of\b"
    r"|\b(?:to\s+)?(?:treat|prevent|reduce\s+the\s+(?:risk|incidence)\s+of"
    r"|decrease\s+the\s+(?:risk|incidence)\s+of|lower\s+the\s+risk\s+of)\b",
    re.IGNORECASE)
_POPULATION_CUE = re.compile(
    r",?\s*\b(?:in|for|among)\s+(?:\w+\s+){0,2}?(?:patients|adults|children|adolescents|infants|"
    r"neonates|subjects|individuals|persons|people|women|men|recipients)\b"
    r"|,?\s*\bat\s+(?:high\s+|increased\s+)?risk\s+(?:of|for)\b"
    r"|,?\s*\b(?:who\s+(?:are|have)\s+)?(?:receiving|undergoing)\b",
    re.IGNORECASE)
_POPULATION_FILLER = {"the", "a", "an", "adult", "adults", "pediatric", "paediatric", "patient",
                      "patients", "children", "and", "or", "of", "in", "for", "with", "aged",
                      "years", "older", "elderly", "who", "are", "have"}

# Organism names used for infections, written as the disease name the ontologies
# use: "Aspergillus and Candida infections" -> "aspergillosis and candidiasis"
ORGANISM_DISEASES = {
    "aspergillus": "aspergillosis", "candida": "candidiasis", "cryptococcus": "cryptococcosis",
    "histoplasma": "histoplasmosis", "coccidioides": "coccidioidomycosis",
    "blastomyces": "blastomycosis", "mucor": "mucormycosis", "mucorales": "mucormycosis",
    "pneumocystis": "pneumocystosis", "toxoplasma": "toxoplasmosis",
    "trichomonas": "trichomoniasis", "giardia": "giardiasis", "fusarium": "fusariosis",
    "scedosporium": "scedosporiosis", "cytomegalovirus": "cytomegalovirus infection",
    "cmv": "cytomegalovirus infection",
}
_GENUS = "|".join(sorted(ORGANISM_DISEASES, key=len, reverse=True))
_ORGANISM_INFECTIONS = re.compile(
    rf"\b((?:{_GENUS})(?:\s*(?:,|and|or|/)\s*(?:{_GENUS}))*)\s+(?:\w+\s+)?infections?\b",
    re.IGNORECASE)

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

        Case-sensitive and applied to the original text (before lowercasing):
        only the upper-case abbreviation is expanded, so ordinary words such as
        "ad" (ad libitum), "ra" (radium Ra 223) or "mi" are left alone.

        Args:
            text (str): The text to process

        Returns:
            str: Text with expanded abbreviations
        """
        for abbr, full in self.bio_abbreviations.items():
            text = re.sub(rf"(?<![\w-]){re.escape(abbr)}(?![\w-])", full, text)
        return text

    def map_organism_infections(self, text):
        """
        "Aspergillus and Candida infections" -> "aspergillosis and candidiasis",
        so that the infection is found in the disease ontologies.
        """
        def repl(m):
            genera = re.findall(_GENUS, m.group(1), flags=re.IGNORECASE)
            names = []
            for g in genera:
                name = ORGANISM_DISEASES[g.lower()]
                if name not in names:
                    names.append(name)
            return " and ".join(names)
        return _ORGANISM_INFECTIONS.sub(repl, text)

    def remove_population_context(self, text):
        """
        Indications section: remove the patient-population part of a statement
        that follows its therapeutic target (see _TARGET_CUE / _POPULATION_CUE),
        up to the end of the statement.

        Args:
            text (str): Original (not yet preprocessed) indications text

        Returns:
            str: Text without the population/risk context
        """
        out, pos = [], 0
        while True:
            target = _TARGET_CUE.search(text, pos)
            if not target:
                break
            end = _STATEMENT_END.search(text, target.end())
            stop = end.start() if end else len(text)
            cue = _POPULATION_CUE.search(text, target.end(), stop)
            if cue:
                between = re.findall(r"[a-z]+", text[target.end():cue.start()].lower())
                if any(w not in _POPULATION_FILLER for w in between):
                    out.append(text[pos:cue.start()])
                    pos = stop
                    continue
            out.append(text[pos:stop])
            pos = stop
        out.append(text[pos:])
        return re.sub(r"\s+", " ", "".join(out)).strip()

    def remove_negated_statements(self, text):
        """
        Remove statements of what a drug is NOT for (Indications section only):
        from a cue such as "not indicated" or "Limitations of Use" to the end of
        its sentence or the next "( 1.2 )" marker.

        Args:
            text (str): Original (not yet preprocessed) text

        Returns:
            str: Text without those statements
        """
        out, pos = [], 0
        for cue in NEGATED_INDICATION_CUES.finditer(text):
            if cue.start() < pos:
                continue
            out.append(text[pos:cue.start()])
            end = _STATEMENT_END.search(text, cue.end())
            pos = end.end() if end else len(text)
        out.append(text[pos:])
        return re.sub(r"\s+", " ", "".join(out)).strip()

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
        # Get standard English stopwords from NLTK, keeping the negations
        standard_stopwords = set(stopwords.words('english')) - NEGATION_WORDS
        standard_stopwords = {w for w in standard_stopwords if not w.endswith("n't")}
        
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
        text = self.correct_abbreviations(text)    # before lowercasing (case-sensitive)
        text = self.normalize_case(text)
        text = self.standardize_punctuation(text)
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
                    text = data[field]
                    if field == 'indications':
                        # what the drug is NOT for must not become an indication,
                        # nor the conditions that only describe the patients
                        text = self.remove_negated_statements(text)
                        text = self.remove_population_context(text)
                    if field in ('indications', 'contraindications'):
                        text = self.map_organism_infections(text)
                    # Replace field with processed text
                    data[field] = self.preprocess_text(text)
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