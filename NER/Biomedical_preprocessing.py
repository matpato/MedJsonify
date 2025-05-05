import re
import json
import string
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk import pos_tag
from owlready2 import get_ontology
import os
from fuzzywuzzy import fuzz  # For better string matching


class BiomedicalPreprocessor:
    """
    A class for preprocessing biomedical text data.
    Includes methods for text normalization, drug name extraction, and disease entity recognition.
    """
    
    def __init__(self):
        """Initialize the BiomedicalPreprocessor with required resources"""
        # Download required NLTK resources
        self._ensure_nltk_resources()
        
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
        
        # Define custom stopwords for biomedical documents
        self.custom_stopwords = [
            "Warnings", "Precautions", "Use", "Specific", "Populations",
            "see", "contraindications", "indications", "dosage", "administration",
            "adverse", "reactions", "drug", "interactions", "clinical", "studies"
        ]
        
        # Load standard stopwords - with handling for the case when they're not yet downloaded
        try:
            self.standard_stopwords = set(stopwords.words('english'))
        except LookupError:
            nltk.download('stopwords')
            self.standard_stopwords = set(stopwords.words('english'))
        
        # Initialize ontology dictionary
        self.disease_terms_dict = {}

    def _ensure_nltk_resources(self):
        """Ensure all required NLTK resources are downloaded"""
        resources = [
            'punkt',
            'stopwords',
            'averaged_perceptron_tagger'
        ]
        
        for resource_name in resources:
            try:
                # Directly download each required resource 
                nltk.download(resource_name, quiet=True)
                print(f"Successfully downloaded NLTK resource: {resource_name}")
            except Exception as e:
                print(f"Error downloading NLTK resource {resource_name}: {str(e)}")

    def fix_encoding_issues(self, text):
        """
        Fix common encoding issues in text.

        Args:
            text (str): The input text with potential encoding issues

        Returns:
            str: Text with fixed encoding issues
        """
        # Replace common problematic characters
        replacements = {
            '\x92': "'",    # Right single quotation mark
            '\x93': '"',    # Left double quotation mark
            '\x94': '"',    # Right double quotation mark
            '\x96': '-',    # En dash
            '\x97': '-',    # Em dash
            '\xa0': ' ',    # Non-breaking space
            '&amp;': '&',   # HTML ampersand
            '&lt;': '<',    # HTML less than
            '&gt;': '>',    # HTML greater than
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def standardize_punctuation(self, text, keep_punctuation=True):
        """
        Standardize punctuation in text.

        Args:
            text (str): The input text
            keep_punctuation (bool): Whether to keep biomedically relevant punctuation

        Returns:
            str: Text with standardized punctuation
        """
        if keep_punctuation:
            # Replace multiple dashes with single dash (but keep the dash)
            text = re.sub(r'-+', '-', text)

            # Ensure spaces around punctuation except for specific cases
            # Keep punctuation in patterns like "COVID-19", "5-HTP", "50mg"
            for punct in [',', '.', ';', ':', '!', '?']:
                text = re.sub(f'(?<![A-Za-z0-9]){re.escape(punct)}', f' {punct} ', text)

            # Standardize parentheses with spaces
            text = re.sub(r'\(', ' ( ', text)
            text = re.sub(r'\)', ' ) ', text)

            # Fix spaces
            text = re.sub(r'\s+', ' ', text)
        else:
            # Remove punctuation entirely (not recommended for biomedical NER)
            text = text.translate(str.maketrans('', '', string.punctuation))

        return text.strip()

    def normalize_case(self, text, preserve_case=False):
        """
        Normalize the case of text.

        Args:
            text (str): The input text
            preserve_case (bool): Whether to preserve the original case

        Returns:
            str: Text with normalized case
        """
        if not preserve_case:
            text = text.lower()
        return text

    def expand_abbreviations(self, text, abbreviations=None):
        """
        Expand common biomedical abbreviations.

        Args:
            text (str): The input text
            abbreviations (dict): Dictionary of abbreviations and their expanded forms

        Returns:
            str: Text with expanded abbreviations
        """
        if abbreviations is None:
            abbreviations = self.bio_abbreviations
            
        # Create case-insensitive dictionary (all keys to lowercase)
        abbrev_lower = {k.lower(): v for k, v in abbreviations.items()}

        # Tokenize with word boundaries to handle punctuation
        words = re.findall(r'\b\w+\b', text)

        for word in words:
            lower_word = word.lower()

            if lower_word in abbrev_lower:
                # Replace the abbreviation with its expanded form
                pattern = r'\b' + re.escape(word) + r'\b'
                text = re.sub(pattern, abbrev_lower[lower_word], text)

        return text

    def correct_drug_spelling(self, text, spelling_map=None):
        """
        Correct common misspellings of drug names.

        Args:
            text (str): The input text
            spelling_map (dict): Dictionary mapping misspelled drugs to their correct spelling

        Returns:
            str: Text with corrected drug spellings
        """
        if spelling_map is None:
            spelling_map = self.drug_spelling_map
            
        words = text.split()
        for i, word in enumerate(words):
            lower_word = word.lower()
            if lower_word in spelling_map:
                # Replace with correct spelling but preserve case pattern
                if word.isupper():
                    words[i] = spelling_map[lower_word].upper()
                elif word[0].isupper():
                    words[i] = spelling_map[lower_word].capitalize()
                else:
                    words[i] = spelling_map[lower_word]
        return ' '.join(words)

    def remove_stopwords(self, text, custom_stopwords=None):
        """
        Remove stopwords from text.

        Args:
            text (str): The input text
            custom_stopwords (list, optional): List of custom stopwords

        Returns:
            str: Text with stopwords removed
        """
        # Safe tokenization with error handling
        try:
            tokens = text.split()  # Fallback to simple splitting if NLTK fails
            try:
                tokens = word_tokenize(text)
            except LookupError:
                # Try downloading punkt again if it failed
                nltk.download('punkt')
                try:
                    tokens = word_tokenize(text)
                except Exception:
                    # Keep using the simple split if it still fails
                    pass
        except Exception as e:
            print(f"Error in tokenization: {str(e)}")
            tokens = text.split()  # Simple fallback

        # Filter out standard stopwords
        filtered_tokens = [token for token in tokens if token.lower() not in self.standard_stopwords]

        # Filter out custom stopwords if provided
        if custom_stopwords:
            custom_stopwords_lower = [word.lower() for word in custom_stopwords]
            filtered_tokens = [token for token in filtered_tokens
                              if token.lower() not in custom_stopwords_lower]
        elif self.custom_stopwords:
            # Use the default custom stopwords
            custom_stopwords_lower = [word.lower() for word in self.custom_stopwords]
            filtered_tokens = [token for token in filtered_tokens
                              if token.lower() not in custom_stopwords_lower]

        # Join tokens back into text
        return ' '.join(filtered_tokens)

    def preprocess_text(self, text, preserve_case=False, keep_punctuation=True,
                      remove_stops=True, custom_stopwords=None):
        """
        Apply all preprocessing steps to the input text.

        Args:
            text (str): The input text
            preserve_case (bool): Whether to preserve the original case
            keep_punctuation (bool): Whether to keep biomedically relevant punctuation
            remove_stops (bool): Whether to remove stopwords
            custom_stopwords (list): Custom stopwords to remove

        Returns:
            str: Fully preprocessed text
        """
        if not text or not isinstance(text, str):
            return ""

        # Apply preprocessing steps in sequence
        text = self.fix_encoding_issues(text)
        text = self.standardize_punctuation(text, keep_punctuation)

        text = self.expand_abbreviations(text)
        text = self.correct_drug_spelling(text)

        if not preserve_case:
            text = self.normalize_case(text)

        # Remove stopwords if specified
        if remove_stops:
            text = self.remove_stopwords(text, custom_stopwords)

        # Ensure clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def process_json_file(self, input_file_path, output_file_path, fields_to_process=None,
                        preserve_case=False, keep_punctuation=True, remove_stops=True):
        """
        Process text fields in a JSON file.

        Args:
            input_file_path (str): Path to the input JSON file
            output_file_path (str): Path to save the processed JSON file
            fields_to_process (list): List of specific fields to process
            preserve_case (bool): Whether to preserve the original case
            keep_punctuation (bool): Whether to keep biomedically relevant punctuation
            remove_stops (bool): Whether to remove stopwords
        """
        # Load the JSON file
        try:
            with open(input_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except Exception as e:
            print(f"Error loading JSON file {input_file_path}: {str(e)}")
            return

        # If specific fields are provided, only process those
        if fields_to_process:
            for field in fields_to_process:
                if field in data and isinstance(data[field], str):
                    # Store original field value
                    data[f"{field}_original"] = data[field]

                    # Apply text preprocessing with exception handling
                    try:
                        data[field] = self.preprocess_text(
                            data[field],
                            preserve_case=preserve_case,
                            keep_punctuation=keep_punctuation,
                            remove_stops=remove_stops,
                            custom_stopwords=self.custom_stopwords
                        )
                    except Exception as e:
                        print(f"Error processing field {field}: {str(e)}")
                        # Keep original if processing fails
                        data[field] = data[f"{field}_original"]
        else:
            # Process all string fields in the JSON
            try:
                processed_data = self.process_json_object(
                    data,
                    preserve_case=preserve_case,
                    keep_punctuation=keep_punctuation,
                    remove_stops=remove_stops,
                    custom_stopwords=self.custom_stopwords
                )
                data = processed_data
            except Exception as e:
                print(f"Error in recursive JSON processing: {str(e)}")

        # Save the processed JSON
        try:
            with open(output_file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
            print(f"Processed JSON saved to {output_file_path}")
        except Exception as e:
            print(f"Error saving processed JSON to {output_file_path}: {str(e)}")

    def process_json_object(self, obj, preserve_case=False, keep_punctuation=True,
                          remove_stops=True, custom_stopwords=None):
        """
        Recursively process a JSON object, preprocessing text fields.

        Args:
            obj: JSON object (dict, list, or primitive value)
            preserve_case (bool): Whether to preserve the original case
            keep_punctuation (bool): Whether to keep biomedically relevant punctuation
            remove_stops (bool): Whether to remove stopwords
            custom_stopwords (list): Custom stopwords to remove

        Returns:
            The processed JSON object
        """
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if isinstance(value, str):
                    # Preprocess text fields
                    result[f"{key}_original"] = value
                    try:
                        result[key] = self.preprocess_text(
                            value,
                            preserve_case=preserve_case,
                            keep_punctuation=keep_punctuation,
                            remove_stops=remove_stops,
                            custom_stopwords=custom_stopwords
                        )
                    except Exception as e:
                        print(f"Error preprocessing field {key}: {str(e)}")
                        result[key] = value  # Keep original on error
                else:
                    # Recursively process non-string fields
                    result[key] = self.process_json_object(
                        value,
                        preserve_case=preserve_case,
                        keep_punctuation=keep_punctuation,
                        remove_stops=remove_stops,
                        custom_stopwords=custom_stopwords
                    )
            return result
        elif isinstance(obj, list):
            return [self.process_json_object(
                item,
                preserve_case=preserve_case,
                keep_punctuation=keep_punctuation,
                remove_stops=remove_stops,
                custom_stopwords=custom_stopwords
            ) for item in obj]
        else:
            # Return primitive values unchanged
            return obj

    def extract_drug_names(self, text):
        """
        Extract drug names from text using rule-based patterns
        
        Args:
            text (str): The input text
            
        Returns:
            list: List of extracted drug names
        """
        # Common drug name suffixes by class
        drug_patterns = [
            r'\b\w+(?:mab|ximab|zumab|umab)\b',  # Monoclonal antibodies
            r'\b\w+(?:tinib|pib|nib|fib)\b',  # Kinase inhibitors
            r'\b\w+(?:olol)\b',  # Beta blockers
            r'\b\w+(?:pril|sartan)\b',  # ACE inhibitors and ARBs
            r'\b\w+(?:oxacin|cycline|cillin)\b',  # Antibiotics
            r'\b\w+(?:zepam|azepam|azolam)\b',  # Benzodiazepines
            r'\b\w+(?:statin)\b',  # Statins
            r'\b\w+(?:conazole)\b',  # Antifungals
            r'\b\w+(?:zosin)\b',  # Alpha blockers
            r'\b\w+(?:dipine|pazil)\b',  # Calcium channel blockers
            r'\b\w+(?:barb)\b',  # Barbiturates
            r'\b\w+(?:navir)\b',  # HIV protease inhibitors
            r'\b\w+(?:setron)\b',  # 5-HT3 antagonists

            # Common drug patterns with capitalization
            r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b',  # CamelCase drug names
            r'\b[A-Z][a-z]+\b'  # Capitalized words (potential brand names)
        ]

        # Find all matches
        all_matches = []
        for pattern in drug_patterns:
            matches = re.findall(pattern, text)
            all_matches.extend(matches)

        # Common words to exclude (non-drug words that might match patterns)
        exclude_words = ['section', 'system', 'central', 'nervous', 'treatment',
                         'therapy', 'usage', 'patients', 'studies', 'clinical',
                         'indication', 'contraindication', 'reaction']

        # Filter results
        filtered_matches = [m for m in all_matches
                           if m.lower() not in exclude_words
                           and len(m) > 3]

        # Remove duplicates while preserving order
        unique_matches = []
        for match in filtered_matches:
            if match not in unique_matches:
                unique_matches.append(match)

        return unique_matches

    def extract_disease_entities(self, text):
        """
        Extract disease entities from biomedical text
        
        Args:
            text (str): The input text
            
        Returns:
            list: List of extracted disease entities
        """
        # Pre-process text
        try:
            sentences = sent_tokenize(text)
        except Exception:
            # Simple fallback if NLTK tokenization fails
            sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

        # Generic patterns for disease entities that handle hyphenated terms
        disease_patterns = [
            r'(?:invasive|severe)\s+[\w-]+\s+infections?',
            r'[\w-]+\s+(?:disease|disorder|syndrome|deficiency)',
            r'(?:acute|chronic)\s+[\w-]+\s+[\w-]+',
            r'[\w-]+(?:-versus-[\w-]+)?\s+disease',
            r'[\w-]+\s+malignancies',
            r'invasive\s+(?:[\w-]+)\s+infections?',
            r'[\w-]+\s+leukemia',
            r'[\w-]+\s+lymphoma',
            r'[\w-]+\s+lysis\s+syndrome',
            r'(?:hyper|hypo)[\w-]+emia'
        ]

        # Find disease mentions
        disease_mentions = []

        # Search using general patterns
        for pattern in disease_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            disease_mentions.extend(matches)

        # Use NLP approach for more complex extractions with robust error handling
        for sentence in sentences:
            try:
                # First, preserve hyphenated terms by temporarily replacing hyphens with a special marker
                preserved_sentence = re.sub(r'(\w+)-(\w+)', r'\1_HYPHEN_\2', sentence)

                # Now tokenize with standard tokenizer or fallback
                try:
                    tokens = word_tokenize(preserved_sentence)
                except Exception:
                    # Simple fallback tokenization
                    tokens = preserved_sentence.split()

                # Restore hyphens
                tokens = [token.replace('_HYPHEN_', '-') for token in tokens]

                # Apply POS tagging with error handling
                try:
                    tagged = pos_tag(tokens)
                except LookupError:
                    nltk.download('averaged_perceptron_tagger')
                    try:
                        tagged = pos_tag(tokens)
                    except Exception:
                        # If POS tagging fails, use a simple heuristic approach
                        continue
                except Exception:
                    continue

                # Build noun phrases
                current_np = []
                noun_phrases = []

                for word, tag in tagged:
                    if tag.startswith('JJ') or tag.startswith('NN'):
                        current_np.append(word)
                    elif current_np:
                        if len(current_np) > 1:  # Only keep multi-word phrases
                            noun_phrases.append(' '.join(current_np))
                        current_np = []

                if current_np and len(current_np) > 1:
                    noun_phrases.append(' '.join(current_np))

                # Filter noun phrases to find disease candidates
                disease_indicators = ['disease', 'disorder', 'syndrome', 'infection',
                                     'deficiency', 'malignancy', 'cancer', 'leukemia',
                                     'lymphoma', 'transplant', 'neutropenia']

                for np in noun_phrases:
                    if any(indicator in np.lower() for indicator in disease_indicators):
                        disease_mentions.append(np)
            except Exception as e:
                print(f"Error processing sentence for disease extraction: {str(e)}")
                continue

        # Remove duplicates and normalize
        unique_diseases = []
        for disease in disease_mentions:
            normalized = disease.lower().strip()
            if normalized not in [d.lower() for d in unique_diseases] and len(normalized) > 3:
                unique_diseases.append(disease)

        return unique_diseases

    def load_disease_ontology(self, ontology_path=None):
        """
        Load the disease ontology and create a lookup dictionary
        
        Args:
            ontology_path (str): Path to the ontology file (if None, will use default URL)
            
        Returns:
            dict: Dictionary mapping disease terms to their IRIs
        """
        try:
            print("Loading ORDO ontology...")
            if ontology_path and os.path.exists(ontology_path):
                onto = get_ontology(ontology_path).load()
            else:
                onto = get_ontology("https://www.orphadata.com/data/ontologies/ordo/last_version/ORDO_en_4.6.owl").load()
            print("Ontology loaded successfully.")
            
            # Create lookup dictionary
            for cls in onto.classes():
                if hasattr(cls, "label") and cls.label:
                    for label in cls.label:
                        self.disease_terms_dict[label.lower()] = cls.iri

                # Add synonyms
                for prop in ["hasExactSynonym", "hasRelatedSynonym", "hasNarrowSynonym"]:
                    if hasattr(cls, prop):
                        for synonym in getattr(cls, prop):
                            self.disease_terms_dict[synonym.lower()] = cls.iri
                            
            return self.disease_terms_dict
            
        except Exception as e:
            print(f"Error loading ontology: {e}")
            return {}


    def find_disease_in_ontology(self, disease_name, disease_terms_dict=None):
        """
        Find a disease in the ontology using the prebuilt dictionary with fuzzy matching.
        
        Args:
            disease_name (str): Name of the disease to find
            disease_terms_dict (dict): Dictionary mapping disease terms to IRIs
            
        Returns:
            str: IRI of the disease if found, None otherwise
        """
        if disease_terms_dict is None:
            if not self.disease_terms_dict:
                self.load_disease_ontology()
            disease_terms_dict = self.disease_terms_dict

        search_name = disease_name.lower()

        # Try exact match first
        if search_name in disease_terms_dict:
            return disease_terms_dict[search_name]

        # Try fuzzy matching with more advanced scoring
        best_match = None
        best_score = 0

        for term, term_id in disease_terms_dict.items():
            # Use fuzzy string matching for better results
            ratio = fuzz.token_sort_ratio(search_name, term)

            if ratio > best_score:
                best_score = ratio
                best_match = term_id

        # Use a higher threshold for more confident matches
        if best_score >= 80:
            return best_match

        return None

    def process_drug_label(self, file_path):
        """
        Process a single drug label JSON file to extract drugs and diseases
        
        Args:
            file_path (str): Path to the JSON file
            
        Returns:
            dict: Dictionary containing extracted information
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading drug label JSON file {file_path}: {str(e)}")
            return {
                'file': os.path.basename(file_path),
                'error': str(e)
            }

        # Extract sections of interest
        indications = data.get("indications", '')
        contraindications = data.get("contraindications", '')

        # Extract the main drug name
        main_drug = data.get('name', '').strip()

        # Extract additional drug names from the text with error handling
        try:
            indications_drugs = self.extract_drug_names(indications)
        except Exception as e:
            print(f"Error extracting drugs from indications: {str(e)}")
            indications_drugs = []

        try:
            contraindications_drugs = self.extract_drug_names(contraindications)
        except Exception as e:
            print(f"Error extracting drugs from contraindications: {str(e)}")
            contraindications_drugs = []

        # Extract disease mentions with error handling
        try:
            indications_diseases = self.extract_disease_entities(indications)
        except Exception as e:
            print(f"Error extracting diseases from indications: {str(e)}")
            indications_diseases = []

        try:
            contraindications_diseases = self.extract_disease_entities(contraindications)
        except Exception as e:
            print(f"Error extracting diseases from contraindications: {str(e)}")
            contraindications_diseases = []

        # Ensure ontology is loaded
        if not self.disease_terms_dict:
            try:
                self.load_disease_ontology()
            except Exception as e:
                print(f"Error loading disease ontology: {str(e)}")
        
        # Find diseases in ontology with error handling
        indications_disease_ids = []
        for disease in indications_diseases:
            try:
                disease_id = self.find_disease_in_ontology(disease)
                if disease_id:
                    indications_disease_ids.append((disease, disease_id))
            except Exception as e:
                print(f"Error finding disease {disease} in ontology: {str(e)}")

        contraindications_disease_ids = []
        for disease in contraindications_diseases:
            try:
                disease_id = self.find_disease_in_ontology(disease)
                if disease_id:
                    contraindications_disease_ids.append((disease, disease_id))
            except Exception as e:
                print(f"Error finding disease {disease} in ontology: {str(e)}")

        return {
            'file': os.path.basename(file_path),
            'main_drug': main_drug,
            'indication_drugs': indications_drugs,
            'contraindication_drugs': contraindications_drugs,
            'indication_diseases': indications_diseases,
            'indication_disease_ids': indications_disease_ids,
            'contraindication_diseases': contraindications_diseases,
            'contraindication_disease_ids': contraindications_disease_ids
        }

    def process_directory(self, directory_path):
        """
        Process all JSON files in a directory
        
        Args:
            directory_path (str): Path to the directory containing JSON files
            
        Returns:
            list: List of dictionaries containing extracted information
        """
        results = []
        try:
            for filename in os.listdir(directory_path):
                if filename.endswith('.json'):
                    file_path = os.path.join(directory_path, filename)
                    try:
                        result = self.process_drug_label(file_path)
                        results.append(result)
                    except Exception as e:
                        print(f"Error processing file {filename}: {str(e)}")
                        results.append({
                            'file': filename,
                            'error': str(e)
                        })
        except Exception as e:
            print(f"Error processing directory {directory_path}: {str(e)}")
            
        return results


# Example usage
if __name__ == "__main__":
    # Create an instance of the preprocessor
    preprocessor = BiomedicalPreprocessor()
    
    # Example usage for processing a JSON file
    input_file = "sample_data/0bdf77ae-3639-49c1-b7c7-533f9d073084.json"
    output_file = "sample_data/0bdf77ae-3639-49c1-b7c7-533f9d073084_clean.json"
    
    # Process only specific fields
    fields_to_process = ["contraindications", "indications", "warningsAndPrecautions", "adverseReactions"]
    
    # Process the JSON file
    preprocessor.process_json_file(
        input_file,
        output_file,
        fields_to_process=fields_to_process,
        preserve_case=False,
        keep_punctuation=True,
        remove_stops=True
    )