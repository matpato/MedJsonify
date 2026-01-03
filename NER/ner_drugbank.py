"""
DrugBank NER Module
===================
Objective: Enrich pharmaceutical data by matching drug names with DrugBank IDs using fuzzy matching.

This script:
1. Loads and normalizes DrugBank vocabulary data from reference CSV files
2. Creates a searchable dictionary of drug names and their synonyms
3. Processes drug information to identify drug names
4. Uses advanced fuzzy matching algorithms (Jaro-Winkler) to find the closest match in DrugBank
5. Enhances data by adding DrugBank IDs to improve interoperability

The purpose is to standardize drug references across datasets by linking them to authoritative
identifiers, enabling more accurate data integration and analysis in pharmaceutical applications.
"""

import json
import pandas as pd
import os
import re
from rdkit import Chem
from Levenshtein import jaro_winkler
from functools import lru_cache

# ---------------------------------------------------------------------------------------- #
# File Loading Functions
# ---------------------------------------------------------------------------------------- #

def load_drug_data(file_path: str):
    """
    Load drug data from a JSON file.
    
    Args:
        file_path (str): Path to the JSON file
        
    Returns:
        dict or list: The loaded drug data
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)
    
def remove_duplicates(string, delim='; '):
    """
    Remove duplicate items from a delimited string.
    
    Args:
        string (str): The input string with delimited items
        delim (str): The delimiter used in the string
        
    Returns:
        str: A string with duplicates removed
    """
    if not string:
        return ''
    items = string.split(delim)
    unique_items = set(items)
    return delim.join(sorted(unique_items)).strip(delim)

# ---------------------------------------------------------------------------------------- #
# DrugBank Data Processing
# ---------------------------------------------------------------------------------------- #

def load_drugbank_data(drugbank_file: str):
    """
    Load and preprocess DrugBank data from a CSV file.
    
    Args:
        drugbank_file (str): Path to the DrugBank CSV file
        
    Returns:
        pandas.DataFrame: Preprocessed DrugBank data with standardized columns
    """
    # PHASE 1: Load the CSV file
    drugbank = pd.read_csv(drugbank_file, encoding='ISO-8859-1')
    
    # PHASE 2: Verify that all required columns are present
    expected_columns = ['DrugBank ID', 'Common name', 'Synonyms']
    available_columns = drugbank.columns.tolist()
    
    missing_columns = [col for col in expected_columns if col not in available_columns]
    if missing_columns:
        raise ValueError(f"Missing expected columns in DrugBank file: {missing_columns}")
    
    # PHASE 3: Select only the needed columns and rename them to a standardized format
    drugbank = drugbank[expected_columns]
    drugbank.rename(columns={
        'DrugBank ID': 'DRUGBANK_ID', 
        'Common name': 'GENERIC_NAME', 
        'Synonyms': 'SYNONYMS'
    }, inplace=True)
    
    # PHASE 4: Preprocess the data: split synonyms into lists and normalize generic names
    drugbank['SYNONYMS'] = drugbank['SYNONYMS'].fillna('').str.lower().str.split(r';\s*')
    drugbank['GENERIC_NAME'] = drugbank['GENERIC_NAME'].fillna('').str.lower().str.strip()
    
    return drugbank

# ---------------------------------------------------------------------------------------- #
# String Similarity Functions
# ---------------------------------------------------------------------------------------- #

@lru_cache(maxsize=10000)
def calculate_similarity(query, term):
    """
    Calculate the similarity between two strings using Jaro-Winkler distance.
    Results are cached to improve performance.
    
    Args:
        query (str): The query string
        term (str): The term to compare against
        
    Returns:
        float: Similarity score between 0 and 1
    """
    return jaro_winkler(query, term)

def find_closest_drug(query, vocabulary, thresh):
    """
    Find the closest matching drug name in the vocabulary based on string similarity.
    
    Args:
        query (str): The drug name to find
        vocabulary (set): Set of drug names and synonyms to search in
        thresh (float): Minimum similarity threshold (0-1)
        
    Returns:
        str or None: The closest matching drug name, or None if no match found above threshold
    """
    # PHASE 1: Normalize the query
    query = query.lower().strip()
    query = re.sub(r" \(.*?\)", "", query)  # Remove content in parentheses
    
    best_match = None
    best_score = 0
    
    # PHASE 2: Find the closest match in the vocabulary
    for term in vocabulary:
        score = calculate_similarity(query, term)
        if score > best_score:
            best_match = term
            best_score = score
    
    print(f"Query: {query}, Best match: {best_match}, Similarity: {best_score}")
    
    # Return the match if score is above threshold, otherwise None
    return best_match if best_score >= thresh else None

# ---------------------------------------------------------------------------------------- #
# Vocabulary and Drug Information Functions
# ---------------------------------------------------------------------------------------- #

def create_vocabulary(drugbank):
    """
    Create a vocabulary set containing all drug names and their synonyms.
    
    Args:
        drugbank (pandas.DataFrame): The preprocessed DrugBank data
        
    Returns:
        set: A set of all drug names and synonyms
    """
    # Create a set with all generic names
    vocabulary = set(drugbank['GENERIC_NAME'])
    
    # Add all synonyms to the set
    for synonyms in drugbank['SYNONYMS']:
        vocabulary.update(synonyms)
        
    return vocabulary

# Cache for drug information to avoid redundant lookups
drug_cache = {} 

def get_drug_info(query, drugbank, vocabulary, thresh=0.88):
    """
    Get DrugBank IDs for a list of drug name queries.
    
    Args:
        query (list): List of drug names to look up
        drugbank (pandas.DataFrame): The preprocessed DrugBank data
        vocabulary (set): Set of drug names and synonyms
        thresh (float): Minimum similarity threshold for matches
        
    Returns:
        list: List of tuples containing (DrugBank ID, generic name) for matching drugs
    """
    results = []
    seen_ids = set()  # To avoid duplicate IDs in results
    
    for q in query:
        # PHASE 1: Normalize query
        q = q.lower().strip()
        
        # PHASE 2: Check cache first to avoid redundant processing
        if q in drug_cache:
            for drug_id, generic_name in drug_cache[q]:
                if drug_id not in seen_ids:
                    results.append((drug_id, generic_name))
                    seen_ids.add(drug_id)
            continue
        
        # PHASE 3: Find the closest match in the vocabulary
        drug = find_closest_drug(q, vocabulary, thresh)
        
        # PHASE 4: Get the DrugBank ID for the matched drug
        match_rows = drugbank[drugbank['GENERIC_NAME'] == drug] if drug else pd.DataFrame()
        drug_matches = [(row['DRUGBANK_ID'], row['GENERIC_NAME']) for _, row in match_rows.iterrows()]
        
        # PHASE 5: Cache the results for future use
        drug_cache[q] = drug_matches 
        results.extend(drug_matches)
    
    return results

# ---------------------------------------------------------------------------------------- #
# Data Processing Functions
# ---------------------------------------------------------------------------------------- #

def process_drug_data(data, drugbank, vocabulary):
    """
    Process drug data to enrich it with DrugBank IDs.
    
    Args:
        data (dict or list): The drug data to process
        drugbank (pandas.DataFrame): The preprocessed DrugBank data
        vocabulary (set): Set of drug names and synonyms
        
    Returns:
        dict or list: The processed drug data with added DrugBank IDs
    """
    name_pattern = re.compile(r" \(.*?\)")  # Pattern to remove parenthetical content
    
    if isinstance(data, list):
        # PHASE 1: Process a list of drug items
        for item in data:
            drug_name = item.get("name", "").strip() or item.get("Proper Name", "").strip()
            if drug_name:
                drug_name = name_pattern.sub("", drug_name)  # Remove parenthetical content
                item["drugbank_id"] = get_drug_info([drug_name], drugbank, vocabulary)
                print(f"Processing: {drug_name} -> {item['drugbank_id']}")
    elif isinstance(data, dict):
        # PHASE 2: Process a single drug item
        drug_name = data.get("name", "").strip() or data.get("Proper Name", "").strip()
        if drug_name:
            drug_name = name_pattern.sub("", drug_name)
            data["drugbank_id"] = get_drug_info([drug_name], drugbank, vocabulary)
            print(f"Processing: {drug_name} -> {data['drugbank_id']}")
    
    return data

def save_drug_data(data, output_file: str):
    """
    Save processed drug data to a JSON file.
    
    Args:
        data (dict or list): The processed drug data
        output_file (str): Path to save the output JSON file
    """
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4)

# ---------------------------------------------------------------------------------------- #
# Main Processing Function
# ---------------------------------------------------------------------------------------- #

def process_folder(input_folder: str, output_folder: str, drugbank_file: str):
    """
    Process all JSON files in a folder to enrich drug data with DrugBank IDs.
    
    Args:
        input_folder (str): Folder containing input JSON files
        output_folder (str): Folder to save processed JSON files
        drugbank_file (str): Path to the DrugBank CSV file
    """
    # PHASE 1: Load and prepare DrugBank data
    print("Loading data from DrugBank...")
    drugbank = load_drugbank_data(drugbank_file)
    vocabulary = create_vocabulary(drugbank)
    
    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)
    
    # PHASE 2: Process each JSON file in the input folder
    print(f"Processing {len(os.listdir(input_folder))} files...")
    for filename in os.listdir(input_folder):
        if filename.endswith(".json"):
            input_file = os.path.join(input_folder, filename)
            output_file = os.path.join(output_folder, filename)
            
            # Load, process, and save each file
            drug_data = load_drug_data(input_file)
            enriched_data = process_drug_data(drug_data, drugbank, vocabulary)
            save_drug_data(enriched_data, output_file)
    
    print("Processing complete!")