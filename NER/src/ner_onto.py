import re
import os
import json
from nltk import pos_tag
from owlready2 import get_ontology
from difflib import SequenceMatcher
from nltk.tokenize import word_tokenize, sent_tokenize

# ---------------------------------------------------------------------------------------- #

def load_ordo():
    print("Loading ORDO ontology...")
    onto = get_ontology("https://www.orphadata.com/data/ontologies/ordo/last_version/ORDO_en_4.6.owl").load()
    print("Ontology loaded successfully.")
    return onto

# ---------------------------------------------------------------------------------------- #

def build_disease_dictionary(onto):
    disease_terms = {}
    for cls in onto.classes():
        if hasattr(cls, "label") and cls.label:
            for label in cls.label:
                disease_terms[label.lower()] = cls.iri
        for prop in ["hasExactSynonym", "hasRelatedSynonym", "hasNarrowSynonym"]:
            if hasattr(cls, prop):
                for synonym in getattr(cls, prop):
                    disease_terms[synonym.lower()] = cls.iri
    return disease_terms

# ---------------------------------------------------------------------------------------- #

def find_disease_in_ontology(disease_name, disease_terms):
    search_name = disease_name.lower()
    
    if search_name in disease_terms:
        return disease_terms[search_name]
    
    best_match = None
    highest_similarity = 0.0
    for term, iri in disease_terms.items():
        similarity = SequenceMatcher(None, search_name, term).ratio()
        if similarity > highest_similarity and similarity > 0.6:  
            best_match = iri
            highest_similarity = similarity
    
    if best_match:
        print(f"Approximate match found: {disease_name} -> {best_match} (similarity: {highest_similarity:.2f})")
        return best_match
    
    print(f"Disease not found in ontology: {disease_name}")
    return None

# ---------------------------------------------------------------------------------------- #

def extract_disease_entities(text):
    disease_patterns = [
        r'\b\w+(?:disease|syndrome|disorder|deficiency|infection|malignancy|cancer|leukemia|lymphoma)\b',
        r'(?:acute|chronic|severe|invasive)\s+\w+\s+\w+',
        r'\b\w+-\w+\s+(?:disease|syndrome|disorder|infection)\b',
        r'\b\w+\s+versus-host\s+disease\b',  
        r'\bNiemann-Pick\s+disease\b'       
    ]
    matches = []
    for pattern in disease_patterns:
        matches.extend(re.findall(pattern, text, re.IGNORECASE))
    return list(set(matches)) 

# ---------------------------------------------------------------------------------------- # 

"""
def process_json_file(file_path, disease_terms):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Process "indications"
    indications = data.get("indications", "")
    indication_diseases = extract_disease_entities(indications)
    print(f"Extracted indication diseases: {indication_diseases}")
    indication_disease_ids = {
        disease: find_disease_in_ontology(disease, disease_terms)
        for disease in indication_diseases
    }
    print(f"Mapped indication diseases: {indication_disease_ids}")

    # Add orphanet_id field to "indications"
    data["indications_orphanet_ids"] = [
        {"disease": disease, "orphanet_id": disease_id}
        for disease, disease_id in indication_disease_ids.items()
        if disease_id
    ]

    # Process "contraindications"
    contraindications = data.get("contraindications", "")
    contraindication_diseases = extract_disease_entities(contraindications)
    print(f"Extracted contraindication diseases: {contraindication_diseases}")
    contraindication_disease_ids = {
        disease: find_disease_in_ontology(disease, disease_terms)
        for disease in contraindication_diseases
    }
    print(f"Mapped contraindication diseases: {contraindication_disease_ids}")

    # Add orphanet_id field to "contraindications"
    data["contraindications_orphanet_ids"] = [
        {"disease": disease, "orphanet_id": disease_id}
        for disease, disease_id in contraindication_disease_ids.items()
        if disease_id
    ]

    return data

def process_directory(input_dir, output_dir, disease_terms):
    os.makedirs(output_dir, exist_ok=True)
    for filename in os.listdir(input_dir):
        if filename.endswith(".json"):
            input_file = os.path.join(input_dir, filename)
            output_file = os.path.join(output_dir, filename)
            print(f"Processing file: {input_file}")
            processed_data = process_json_file(input_file, disease_terms)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, indent=4, ensure_ascii=False)
            print(f"Results saved to {output_file}")
"""
