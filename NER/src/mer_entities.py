"""
MER Entities Processing
=======================
Objective: Process drug data files by enriching them with entity identifiers 
from ontologies (ChEBI, DrugBank, DOID, Orphanet) for drugs, ingredients and disease indications.

This script:
1. Loads ontology data from MER (Minimal Entity Recognition)
2. Processes drug JSON files to extract drug names and related entities
3. Adds ontology identifiers to each entity
4. Saves the enriched data for further processing
"""

import os
import json
import configparser
from NER.src.Utils.utils import *
from NER.src.Utils.utils2mer import *
from NER.src.ner_drugbank import load_drugbank_data, create_vocabulary, get_drug_info

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
    # Query MER to find entities in the specified ontology
    onto_entities = merpy.get_entities(name, onto)
    
    # Return the identifier if entities found and have sufficient data
    return onto_entities[0][3] if onto_entities and len(onto_entities[0]) > limit else None

# ---------------------------------------------------------------------------------------- #
# Drug Data Processing Functions 
# ---------------------------------------------------------------------------------------- #

def process_drug_data(drug_data, drugbank, vocabulary):
    """
    Process a single drug data object, enriching it with ontology identifiers.
    
    Args:
        drug_data (dict): Drug data to process
        drugbank (DataFrame): DrugBank reference data
        vocabulary (set): Drug name vocabulary for matching
        
    Returns:
        dict: Processed drug data with added identifiers
    """
    # PHASE 1: Extract drug name from data
    drug_name = drug_data.get('name', '') or drug_data.get('Proper Name', '')
    
    # PHASE 2: Try to get ChEBI ID for the drug
    drug_chebi_id = get_onto_id(drug_name, onto='chebi') if drug_name else None
    
    # PHASE 3: Create drug entry with identifier
    if 'name' in drug_data or 'Proper Name' in drug_data:
        drug_data['drug'] = [{
            'name': drug_name,
            'chebi_id': drug_chebi_id
        }]
        
        # PHASE 4: Lookup in DrugBank if no ChEBI ID found
        if drug_chebi_id is None:
            drugbank_info = get_drug_info([drug_name], drugbank, vocabulary)
            if drugbank_info:
                drug_data['drug'][0]['drugbank_id'] = drugbank_info[0][0]

        # PHASE 5: Clean up original fields
        if 'name' in drug_data:
            del drug_data['name']
        if 'Proper Name' in drug_data:
            del drug_data['Proper Name']

    # PHASE 6: Process ingredients (if any)
    for ingredient in drug_data.get('ingredients', []):
        # Try to get ChEBI ID for each ingredient
        ingredient['chebi_id'] = get_onto_id(ingredient['name'], onto='chebi')  
        
        # Lookup in DrugBank if no ChEBI ID found
        if ingredient['chebi_id'] is None:
            drugbank_info = get_drug_info([ingredient['name']], drugbank, vocabulary)
            if drugbank_info:
                ingredient['drugbank_id'] = drugbank_info[0][0]

    # PHASE 7: Process disease-related sections
    for section in ['indications', 'contraindications']:
        text = drug_data.get(section, '')
        if text:
            # Replace text with structured data including ontology IDs
            drug_data[section] = [{
                'text': text,
                'doid_id': get_onto_id(text, onto='do'),  # Disease Ontology ID
                'orphanet_id': get_onto_id(text, onto='ordo')  # Orphanet (rare disease) ID
            }]

    return drug_data

# ---------------------------------------------------------------------------------------- #
# File Processing Functions
# ---------------------------------------------------------------------------------------- #

def process_drug_file(file_path, output_dir, drugbank, vocabulary):
    """
    Process a single drug data file.
    
    Args:
        file_path (str): Path to input JSON file
        output_dir (str): Directory to save output file
        drugbank (DataFrame): DrugBank reference data
        vocabulary (set): Drug name vocabulary for matching
    """
    # Load the input file
    with open(file_path, 'r') as f:
        drug_data = json.load(f)

    # Process the drug data
    processed_data = process_drug_data(drug_data, drugbank, vocabulary)
    
    # Save the processed data
    output_path = os.path.join(output_dir, os.path.basename(file_path))
    with open(output_path, 'w') as f_out:
        json.dump(processed_data, f_out, indent=4)

    print(f"Processed: {file_path}")

# ---------------------------------------------------------------------------------------- #
# Main Function
# ---------------------------------------------------------------------------------------- #

def main(active_lexicon, input_dir, output_dir, update, drugbank_file):
    """
    Main function to process all drug data files in a directory.
    
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

    # PHASE 2: Load DrugBank data
    drugbank = load_drugbank_data(drugbank_file)
    vocabulary = create_vocabulary(drugbank)

    # PHASE 3: Process each JSON file in the input directory
    for filename in os.listdir(input_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(input_dir, filename)
            process_drug_file(file_path, output_dir, drugbank, vocabulary)

# ---------------------------------------------------------------------------------------- #
# Script Entry Point
# ---------------------------------------------------------------------------------------- #

if __name__ == '__main__':
    # Load configuration from config file
    config = configparser.ConfigParser()
    config.read('/opt/airflow/dags/NER/src/config.ini')
    
    # Get configuration parameters
    active_lexicon = config['ONTO']['active_lexicons'].replace(' ', '').split(',')
    input_dir, output_dir = create_entities_folder(src=config['PATH']['path_to_original_json'])
    update = config['ONTO'].get('update')
    drugbank_file = config['PATH']['path_to_drugbank_csv']
    
    # Run the main processing function
    main(active_lexicon, input_dir, output_dir, update, drugbank_file)