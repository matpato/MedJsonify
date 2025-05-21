"""
MER Entities Batch Processing
============================
Objective: Process multiple drug data files in batch mode, enriching them with entity identifiers 
from various ontologies (ChEBI, DrugBank, DOID, Orphanet) using parallelized processing.

This script:
1. Loads ontology data and builds dictionaries for lookup
2. Processes all JSON files in a directory tree
3. Adds ontology identifiers to drugs and diseases
4. Performs concurrent processing for better performance
"""

import os
import json
import configparser
import sys
from concurrent.futures import ThreadPoolExecutor
from NER.src.Utils.utils import *
from NER.src.Utils.utils2mer import *
from NER.src.ner_drugbank import load_drugbank_data, create_vocabulary, get_drug_info
from NER.src.ner_onto import load_ordo, build_disease_dictionary, extract_disease_entities, find_disease_in_ontology

# Add MER library to path
repo_path = os.path.abspath("/opt/airflow/dags/NER/merpy/merpy")
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)
import merpy

# ---------------------------------------------------------------------------------------- #
# Entity Identification Functions
# ---------------------------------------------------------------------------------------- #

def get_onto_id(name, onto='chebi', limit=0):
    """
    Get ontology identifier for an entity name from the specified ontology.
    
    Args:
        name (str): Entity name to look up
        onto (str): Ontology to search in ('chebi', 'do', 'ordo', etc.)
        limit (int): Minimum number of elements required in entity
        
    Returns:
        str or None: Ontology identifier if found, None otherwise
    """
    # Query the MER tool to get entities
    onto_entities = merpy.get_entities(name, onto)
    print(f"Entities for {name} in {onto}: {onto_entities}")  

    # Verify if there are entities and the first one has more than the minimum elements
    if onto_entities and len(onto_entities[0]) > 3 and onto_entities[0][0]:
        return onto_entities[0][3]  # Return the identifier (usually 4th element)
    else:
        print(f"No valid entities found for {name} in {onto}") 
        return None

# ---------------------------------------------------------------------------------------- #
# Drug Data Processing Functions 
# ---------------------------------------------------------------------------------------- #

def process_drug_data(drug_data, drugbank, vocabulary, disease_terms):
    """
    Process a single drug data object, enriching it with ontology identifiers.
    
    Args:
        drug_data (dict): Drug data to process
        drugbank (DataFrame): DrugBank reference data
        vocabulary (set): Drug name vocabulary for matching
        disease_terms (dict): Disease term dictionary from ORDO
        
    Returns:
        dict: Processed drug data with added identifiers
    """
    # PHASE 1: Extract drug name from data
    drug_name = drug_data.get('name', '') or drug_data.get('Proper Name', '')

    # PHASE 2: Try to get ChEBI ID for drug
    drug_chebi_id = get_onto_id(drug_name, onto='chebi') if drug_name else None
    
    # PHASE 3: If no ChEBI ID, try DrugBank lookup
    drugbank_info = None
    if drug_chebi_id is None:
        drugbank_info = get_drug_info([drug_name], drugbank, vocabulary)
        
        # PHASE 4: If still no match and ingredients are available, try first ingredient
        if not drugbank_info and drug_data.get('ingredients'):
            first_ingredient_name = drug_data['ingredients'][0]['name']
            
            drug_name = first_ingredient_name
            
            drug_chebi_id = get_onto_id(drug_name, onto='chebi')
            
            if drug_chebi_id is None:
                drugbank_info = get_drug_info([first_ingredient_name], drugbank, vocabulary)

    # PHASE 5: Build drug entry with identifier
    drug_entry = {'name': drug_name}
    
    if drug_chebi_id:
        drug_entry['chebi_id'] = drug_chebi_id
    elif drugbank_info:
        drug_entry['drugbank_id'] = drugbank_info[0][0]
    
    drug_data['drug'] = [drug_entry]

    # PHASE 6: Clean up original fields
    if 'name' in drug_data:
        del drug_data['name']
    if 'Proper Name' in drug_data:
        del drug_data['Proper Name']

    # PHASE 7: Process ingredients (if any)
    for ingredient in drug_data.get('ingredients', []):
        ingredient['chebi_id'] = get_onto_id(ingredient['name'], onto='chebi') 
        if ingredient['chebi_id'] is None:
            drugbank_info = get_drug_info([ingredient['name']], drugbank, vocabulary)
            if drugbank_info:
                ingredient['drugbank_id'] = drugbank_info[0][0]

    # PHASE 8: Process disease-related sections
    for section in ['indications', 'contraindications']:
        text = drug_data.get(section, '')
        if text:
            # Look up DOID via MER
            doid_id = get_onto_id(text, onto='do')
            
            # Extract and identify Orphanet disease entities
            orphanet_entities = []
            disease_entities = extract_disease_entities(text)
            
            for disease in disease_entities:
                orphanet_id = find_disease_in_ontology(disease, disease_terms)
                if orphanet_id:
                    orphanet_entities.append({"disease": disease, "orphanet_id": orphanet_id})
            
            # Replace text with structured data
            drug_data[section] = [{
                'text': text,
                'doid_id': doid_id,
                'orphanet_entities': orphanet_entities
            }]

    return drug_data

# ---------------------------------------------------------------------------------------- #
# File Processing Functions
# ---------------------------------------------------------------------------------------- #

def process_drug_file(file_path, output_dir, drugbank, vocabulary, disease_terms):
    """
    Process a single drug data file.
    
    Args:
        file_path (str): Path to input JSON file
        output_dir (str): Directory to save output file
        drugbank (DataFrame): DrugBank reference data
        vocabulary (set): Drug name vocabulary for matching
        disease_terms (dict): Disease term dictionary from ORDO
    """
    # Load the input file
    with open(file_path, 'r') as f:
        drug_data = json.load(f)
    
    # Process the drug data
    processed_data = process_drug_data(drug_data, drugbank, vocabulary, disease_terms)

    print(f"Processed data for {file_path}: {processed_data}")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Save the processed data
    output_path = os.path.join(output_dir, os.path.basename(file_path))
    print(f"Saving processed data to: {output_path}")
    
    with open(output_path, 'w') as f_out:
        json.dump(processed_data, f_out, indent=4)

    print(f"File saved: {output_path}")

def process_file_in_batch(args):
    """
    Process a single file as part of batch processing.
    This function is called from ThreadPoolExecutor.
    
    Args:
        args (tuple): Tuple containing (file_path, input_dir, output_dir, drugbank, vocabulary, disease_terms)
    """
    file_path, input_dir, output_dir, drugbank, vocabulary, disease_terms = args
    try:
        # Calculate relative path to maintain directory structure
        relative_path = os.path.relpath(file_path, input_dir)
        output_path = os.path.join(output_dir, relative_path)
        output_dir_for_file = os.path.dirname(output_path)

        print(f"Processing file: {file_path}, Output directory: {output_dir_for_file}")
        process_drug_file(file_path, output_dir_for_file, drugbank, vocabulary, disease_terms)
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")

# ---------------------------------------------------------------------------------------- #
# Main Function
# ---------------------------------------------------------------------------------------- #

def main(active_lexicon, input_dir, output_dir, update, drugbank_file):
    """
    Main function to process drug data files in batch mode.
    
    Args:
        active_lexicon (list): List of ontologies to use
        input_dir (str): Directory containing input files
        output_dir (str): Directory to save output files
        update (str): Whether to update ontologies ('1' for yes)
        drugbank_file (str): Path to DrugBank CSV file
    """
    # PHASE 1: Update ontologies if requested
    if update == '1':
        update_mer(lexicon=active_lexicon)
    else:
        print("Using existing ontologies (no update)")

    # PHASE 2: Load ORDO ontology for disease matching
    print("Loading ORDO ontology and building disease dictionary...")
    onto = load_ordo()
    disease_terms = build_disease_dictionary(onto)
    print(f"Disease dictionary built with {len(disease_terms)} terms")

    # PHASE 3: Load DrugBank data
    drugbank = load_drugbank_data(drugbank_file)
    vocabulary = create_vocabulary(drugbank)

    # PHASE 4: Find all JSON files to process
    files_to_process = []
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith('.json'):
                input_file = os.path.join(root, filename)
                print(f"Adding file to process: {input_file}")
                files_to_process.append((input_file, input_dir, output_dir, drugbank, vocabulary, disease_terms))

    print(f"Total files to process: {len(files_to_process)}")

    # PHASE 5: Process files in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(process_file_in_batch, files_to_process)