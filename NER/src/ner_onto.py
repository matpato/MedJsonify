"""
NER Ontology Module: Disease Entity Recognition and Normalization
----------------------------------------------------------------

This module extracts and normalizes disease entities from text using 
the ORDO (Orphanet Rare Disease Ontology).

The primary objectives are:
1. Load and parse the ORDO ontology for disease terminology access
2. Build a comprehensive dictionary of disease terms with synonyms
3. Extract disease mentions from text using pattern recognition
4. Map extracted disease terms to standardized ontology identifiers
5. Support both exact and fuzzy matching with confidence scores
"""

import re
import os
import json
from nltk import pos_tag
from owlready2 import get_ontology
from difflib import SequenceMatcher
from nltk.tokenize import word_tokenize, sent_tokenize

# -----------------------------------------------------------------------------
# PHASE 1: ONTOLOGY LOADING
# Objective: Download and parse the ORDO ontology to access disease terminology
# -----------------------------------------------------------------------------

def load_ordo():
    """
    Load the ORDO (Orphanet Rare Disease Ontology) from the web.
    
    This function retrieves the latest version of the ORDO ontology
    and loads it into memory using the owlready2 library.
    
    Returns:
        ontology: The loaded ORDO ontology object containing all classes
                 and relationships
    """
    print("Loading ORDO ontology...")
    try:
        onto = get_ontology("https://www.orphadata.com/data/ontologies/ordo/last_version/ORDO_en_4.6.owl").load()
        print("Ontology loaded successfully.")
        return onto
    except Exception as e:
        print(f"Error loading ontology: {e}")
        raise

# -----------------------------------------------------------------------------
# PHASE 2: DICTIONARY CONSTRUCTION
# Objective: Build a comprehensive mapping of disease terms to ontology IRIs
# -----------------------------------------------------------------------------

def build_disease_dictionary(onto):
    """
    Build a comprehensive dictionary of disease terms from the ORDO ontology.
    
    This function iterates through all classes in the ontology and extracts:
    - Primary labels (official disease names)
    - Exact synonyms (alternative but equivalent terms)
    - Related synonyms (closely related terms)
    - Narrow synonyms (more specific terms)
    
    All terms are normalized to lowercase to enable case-insensitive matching.
    
    Args:
        onto: The loaded ORDO ontology object
        
    Returns:
        dict: A dictionary mapping lowercase disease terms to their 
              corresponding ontology IRIs
    """
    disease_terms = {}
    synonym_count = 0
    label_count = 0
    
    # Iterate through all classes in the ontology
    for cls in onto.classes():
        # Add primary labels
        if hasattr(cls, "label") and cls.label:
            for label in cls.label:
                disease_terms[label.lower()] = cls.iri
                label_count += 1
        
        # Add synonyms of different types
        for prop in ["hasExactSynonym", "hasRelatedSynonym", "hasNarrowSynonym"]:
            if hasattr(cls, prop):
                for synonym in getattr(cls, prop):
                    disease_terms[synonym.lower()] = cls.iri
                    synonym_count += 1
    
    print(f"Dictionary built with {label_count} primary labels and {synonym_count} synonyms")
    return disease_terms

# -----------------------------------------------------------------------------
# PHASE 3: ENTITY MATCHING
# Objective: Find disease mentions in the ontology using exact and fuzzy matching
# -----------------------------------------------------------------------------

def find_disease_in_ontology(disease_name, disease_terms, similarity_threshold=0.6):
    """
    Find a disease in the ontology dictionary using exact or fuzzy matching.
    
    The function first attempts an exact match (case-insensitive). If that fails,
    it uses string similarity algorithms to find the closest match above a 
    specified threshold.
    
    Args:
        disease_name (str): The disease name to look up
        disease_terms (dict): Dictionary mapping disease terms to IRIs
        similarity_threshold (float): Minimum similarity score (0-1) for fuzzy matches
        
    Returns:
        str or None: The IRI of the matching disease term, or None if no match found
    """
    # Try exact match first (case-insensitive)
    search_name = disease_name.lower()
    if search_name in disease_terms:
        return disease_terms[search_name]
    
    # If no exact match, try fuzzy matching
    best_match = None
    highest_similarity = 0.0
    
    for term, iri in disease_terms.items():
        # Calculate similarity using SequenceMatcher
        similarity = SequenceMatcher(None, search_name, term).ratio()
        
        # Update if this is the best match so far and exceeds minimum threshold
        if similarity > highest_similarity and similarity > similarity_threshold:
            best_match = iri
            highest_similarity = similarity
    
    if best_match:
        print(f"Approximate match found: {disease_name} -> {best_match} (similarity: {highest_similarity:.2f})")
        return best_match
    
    print(f"Disease not found in ontology: {disease_name}")
    return None

# -----------------------------------------------------------------------------
# PHASE 4: TEXT EXTRACTION
# Objective: Extract potential disease mentions from text using pattern recognition
# -----------------------------------------------------------------------------

def extract_disease_entities(text):
    """
    Extract potential disease mentions from text using regular expression patterns.
    
    This function applies multiple pattern recognition rules designed to identify
    common disease naming conventions, including:
    - Disease terms with specific suffixes (disease, syndrome, disorder)
    - Diseases with severity modifiers (acute, chronic, severe)
    - Hyphenated disease names
    - Complex multi-word disease patterns
    - Explicitly named rare diseases
    
    Args:
        text (str): The input text to analyze
        
    Returns:
        list: List of unique potential disease mentions found in the text
    """
    if not text:
        return []
        
    # Define patterns for disease recognition
    disease_patterns = [
        # Common disease suffixes
        r'\b\w+(?:disease|syndrome|disorder|deficiency|infection|malignancy|cancer|leukemia|lymphoma)\b',
        
        # Diseases with modifiers
        r'(?:acute|chronic|severe|invasive)\s+\w+\s+\w+',
        
        # Hyphenated disease names
        r'\b\w+-\w+\s+(?:disease|syndrome|disorder|infection)\b',
        
        # Specific complex disease patterns
        r'\b\w+\s+versus-host\s+disease\b',
        
        # Explicitly named diseases
        r'\bNiemann-Pick\s+disease\b',
        r'\bGaucher\s+disease\b',
        r'\bFabry\s+disease\b',
        r'\bCystic\s+fibrosis\b',
        r'\bHuntington\'s\s+disease\b',
        r'\bAlzheimer\'s\s+disease\b',
        r'\bParkinson\'s\s+disease\b'
    ]
    
    # Find all matches for each pattern
    matches = []
    for pattern in disease_patterns:
        matches.extend(re.findall(pattern, text, re.IGNORECASE))
    
    # Remove duplicates and return
    unique_matches = list(set(matches))
    print(f"Extracted {len(unique_matches)} potential disease entities")
    return unique_matches

# -----------------------------------------------------------------------------
# PHASE 5: ADVANCED ENTITY PROCESSING (Optional extension)
# Objective: Improve entity recognition through context analysis
# -----------------------------------------------------------------------------

def analyze_disease_context(text, disease_entities):
    """
    Analyze the context around identified disease entities to improve confidence.
    
    This function examines surrounding text for:
    - Medical terminology that supports disease classification
    - Negation terms that might invalidate a match
    - Relationship to treatments or symptoms
    
    Args:
        text (str): The full text being analyzed
        disease_entities (list): Previously identified disease mentions
        
    Returns:
        dict: Enhanced disease entities with context information
    """
    # Split text into sentences for context analysis
    sentences = sent_tokenize(text)
    
    enhanced_entities = []
    
    for disease in disease_entities:
        # Find which sentences contain this disease entity
        containing_sentences = [s for s in sentences if disease.lower() in s.lower()]
        
        # Analyze context
        for sentence in containing_sentences:
            # Check for negation patterns
            negated = any(neg in sentence.lower() for neg in ["no", "not", "without", "absence of", "ruled out"])
            
            # Check for confidence markers
            uncertain = any(unc in sentence.lower() for unc in ["possible", "suspected", "potential", "may have"])
            
            # Look for treatment or symptom associations
            tokens = word_tokenize(sentence)
            pos_tags = pos_tag(tokens)
            
            enhanced_entities.append({
                "entity": disease,
                "context": sentence,
                "negated": negated,
                "uncertain": uncertain
            })
    
    return enhanced_entities

# For easy module testing
if __name__ == "__main__":
    # Test with a sample text
    sample_text = """
    The patient was diagnosed with Niemann-Pick disease type C. 
    There were no signs of cystic fibrosis. However, we cannot rule out 
    a mild form of Gaucher disease based on the enzyme analysis.
    """
    
    # Load ontology and build dictionary
    onto = load_ordo()
    disease_terms = build_disease_dictionary(onto)
    
    # Extract and match disease entities
    diseases = extract_disease_entities(sample_text)
    print(f"Extracted diseases: {diseases}")
    
    for disease in diseases:
        ontology_id = find_disease_in_ontology(disease, disease_terms)
        if ontology_id:
            print(f"Matched '{disease}' to ontology ID: {ontology_id}")
        else:
            print(f"No ontology match found for '{disease}'")
            
    # Advanced context analysis
    enhanced = analyze_disease_context(sample_text, diseases)
    print("Enhanced entities with context:", json.dumps(enhanced, indent=2))