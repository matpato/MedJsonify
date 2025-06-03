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
    # Map simple names to file names used by get_entities.sh
    onto_source_map = {
        'chebi': 'chebi_lite',
        'do': 'doid'
        # Add other mappings if needed
    }
    
    # Get the correct source name from the map
    onto_source = onto_source_map.get(onto, onto) # Use original name if not in map

    # --- START: Change working directory for merpy call ---
    mer_home = os.environ.get('MER_HOME')
    original_cwd = os.getcwd()
    onto_entities = [] # Initialize empty list
    
    if mer_home and os.path.isdir(mer_home):
        try:
            os.chdir(mer_home)
            print(f"Changed working directory to {os.getcwd()} for merpy call.") # Debug print
            # Query the MER tool to get entities
            # Pass the text (name) and the correct source name (onto_source)
            onto_entities = merpy.get_entities(name, onto_source)
            print(f"Entities for '{name}' using source '{onto_source}': {onto_entities}")  
        except Exception as e:
            print(f"Error during merpy call: {e}")
        finally:
            os.chdir(original_cwd) # Always change back
            print(f"Changed working directory back to {os.getcwd()}.") # Debug print
    else:
        print(f"MER_HOME not set or invalid: {mer_home}. Cannot call merpy.")
    # --- END: Change working directory ---

    # The merpy output format is expected to be a list of matches, 
    # where each match is [start, end, matched_text, link_or_id]
    # We are interested in the link/id (index 3) of the first match.
    # Note: The previous print in get_onto_id is now inside the try block.
    if onto_entities and onto_entities[0] and len(onto_entities[0]) > 3:
        identifier = onto_entities[0][3]
        return identifier
    else:
        # The previous print for 'No valid entities found' is now inside the try block.
        return None

# ---------------------------------------------------------------------------------------- #
# Drug Data Processing Functions 
# ---------------------------------------------------------------------------------------- #

def process_drug_data(drug_data, drugbank, vocabulary, disease_terms):
    """
    Process a single drug data object, enriching it with ontology identifiers.
    """
    print(f"Processing drug data for: {drug_data.get('name', drug_data.get('Proper Name', 'Unknown Drug'))}")
    # PHASE 1: Extract drug names
    trade_name = drug_data.get('Trade_Name', '').strip()
    proper_name = drug_data.get('Proper Name', '').strip()
    # ADICIONAR SUPORTE PARA O CAMPO "name"
    generic_name = drug_data.get('name', '').strip()

    # Se não houver nenhum nome, não processa
    if not trade_name and not proper_name and not generic_name:
        return drug_data

    # PHASE 2: Try to get ChEBI ID for drug
    drug_chebi_id = None
    if trade_name:
        drug_chebi_id = get_onto_id(trade_name, onto='chebi')
    if drug_chebi_id is None and proper_name:
        drug_chebi_id = get_onto_id(proper_name, onto='chebi')
    # NOVO: tentar com "name"
    if drug_chebi_id is None and generic_name:
        drug_chebi_id = get_onto_id(generic_name, onto='chebi')

    # PHASE 3: If no ChEBI ID, try DrugBank lookup
    drugbank_info = None
    if drug_chebi_id is None:
        if trade_name:
            drugbank_info = get_drug_info([trade_name], drugbank, vocabulary)
        if not drugbank_info and proper_name:
            drugbank_info = get_drug_info([proper_name], drugbank, vocabulary)
        # NOVO: tentar com "name"
        if not drugbank_info and generic_name:
            drugbank_info = get_drug_info([generic_name], drugbank, vocabulary)
        # PHASE 4: If still no match and ingredients are available, try first ingredient
        if not drugbank_info and drug_data.get('ingredients'):
            first_ingredient = drug_data['ingredients'][0]
            first_ingredient_name = first_ingredient.get('name', '')
            if first_ingredient_name:
                drug_chebi_id = get_onto_id(first_ingredient_name, onto='chebi')
                if drug_chebi_id is None:
                    drugbank_info = get_drug_info([first_ingredient_name], drugbank, vocabulary)

    # PHASE 5: Build drug entry with identifier
    # Use the name that was successful in finding the ID, or generic_name as fallback
    drug_name = proper_name or trade_name or generic_name
    drug_entry = {'name': drug_name}

    if drug_chebi_id:
        drug_entry['chebi_id'] = drug_chebi_id
    elif drugbank_info:
        drug_entry['drugbank_id'] = drugbank_info[0][0]

    drug_data['drug'] = [drug_entry]

    # PHASE 6: Process ingredients (if any)
    for ingredient in drug_data.get('ingredients', []):
        ingredient_name = ingredient.get('name', '')
        if ingredient_name:
            print(f"Processing ingredient: '{ingredient_name}'")
            ingredient['chebi_id'] = get_onto_id(ingredient_name, onto='chebi')
            if ingredient['chebi_id'] is None:
                drugbank_info = get_drug_info([ingredient_name], drugbank, vocabulary)
                if drugbank_info:
                    ingredient['drugbank_id'] = drugbank_info[0][0]

    # PHASE 7: Process disease-related sections
    for section in ['indications', 'contraindications']:
        text = drug_data.get(section, '')
        if text:
            print(f"Processing section '{section}' with text: '{text}'")
            
            # Find DOID entities within the text using get_onto_id with onto='do' source
            # Note: get_onto_id with 'do' source will use 'doid' data files.
            print(f"Calling merpy.get_entities for section '{section}' with source 'doid' and text: '{text}'")
            doid_entities_list = merpy.get_entities(text, 'doid') # Use merpy directly for all matches
            print(f"Output from merpy.get_entities for '{section}' (doid): {doid_entities_list}")

            doid_entities_formatted = []
            if doid_entities_list:
                for entity_match in doid_entities_list:
                    # entity_match is expected to be [start, end, matched_text, link_or_id]
                    if len(entity_match) > 3:
                         doid_entities_formatted.append({
                             'text': entity_match[2], # The matched text
                             'doid_id': entity_match[3] # The DOID identifier/link
                         })

            orphanet_entities = []
            # Keep existing ORDO/Orphanet logic as it seems to be working
            disease_entities_from_text = extract_disease_entities(text)
            for disease in disease_entities_from_text:
                orphanet_id = find_disease_in_ontology(disease, disease_terms)
                if orphanet_id:
                    orphanet_entities.append({"disease": disease, "orphanet_id": orphanet_id})
                    
            # Update the section data in drug_data
            # Store original text, list of found DOID entities, and list of Orphanet entities
            drug_data[section] = [{
                'text': text, # Keep original text
                'doid_entities': doid_entities_formatted, # List of found DOID entities
                'orphanet_entities': orphanet_entities # List of found Orphanet entities (from ORDO)
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