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
import subprocess

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
        For DOIDs, returns a list of matches instead of just the first one
    """
    onto_source_map = {
        'chebi': 'chebi_lite',
        'do': 'doid'
        # Add other mappings if needed
    }
    
    onto_source = onto_source_map.get(onto, onto)

    mer_home = os.environ.get('MER_HOME')
    if not mer_home or not os.path.isdir(mer_home):
        print(f"MER_HOME not set or invalid: {mer_home}. Cannot call merpy script.")
        return None

    script_path = os.path.join(mer_home, 'get_entities.sh')
    if not os.path.exists(script_path):
        print(f"MER script not found at {script_path}")
        return None

    # --- START: Call get_entities.sh directly and parse output ---
    # Construct the command to run the shell script
    command = [script_path, name, onto_source]
    
    onto_entities = []
    try:
        # Execute the command and capture output
        print(f"Executing command: {' '.join(command)} from {os.getcwd()}")
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60, cwd=mer_home)
        print(f"Script output (stdout):\n{result.stdout}")
        print(f"Script output (stderr):\n{result.stderr}")
        
        # Parse the tab-separated output
        for line in result.stdout.strip().split('\n'):
            if line:
                # Split by tab
                parts = line.split('\t')
                if len(parts) == 4:
                    # Append as [start, end, matched_text, link_or_id] list
                    onto_entities.append(parts)
                else:
                    print(f"Warning: Skipping malformed line from script output: {line}")

        print(f"Parsed entities for '{name}' using source '{onto_source}': {onto_entities}")

    except FileNotFoundError:
        print(f"Error: get_entities.sh script not found at {script_path}")
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error executing script: {e}")
        print(f"Stderr: {e.stderr}")
        return None
    except subprocess.TimeoutExpired:
        print(f"Error: Script execution timed out after 60 seconds.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during script execution or parsing: {e}")
        return None
    # --- END: Call get_entities.sh directly and parse output ---

    # For DOIDs, return all matches as a list
    if onto == 'do':
        return onto_entities

    # For other ontologies (like ChEBI), return the first exact match or first match
    exact_match_id = None
    first_found_id = None

    for match in onto_entities:
        # match is [start, end, matched_text, link_or_id]
        if len(match) > 3:
            matched_text = match[2].strip()
            identifier = match[3].strip()

            # Store the first found ID just in case no exact match is found
            if first_found_id is None:
                first_found_id = identifier

            # Check if the matched text is an exact match for the input name
            if matched_text.lower() == name.strip().lower():
                exact_match_id = identifier # Found exact match, this is the preferred ID
                break # Stop searching once an exact match is found

    # Return the exact match ID if found, otherwise return the first found ID
    return exact_match_id if exact_match_id is not None else first_found_id

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

    # NOVO: Extrair o nome do ingrediente
    ingredient_name_field = drug_data.get('Ingredient', '').strip()

    # Se não houver nenhum nome, não processa
    if not trade_name and not proper_name and not generic_name:
        return drug_data

    # PHASE 2: Try to get ChEBI ID for drug
    drug_chebi_id = None
    # Try Ingredient name first as it's more likely to match ChEBI
    if ingredient_name_field:
        drug_chebi_id = get_onto_id(ingredient_name_field, onto='chebi')
    # Then try other names if no match found
    if drug_chebi_id is None and trade_name:
        drug_chebi_id = get_onto_id(trade_name, onto='chebi')
    if drug_chebi_id is None and proper_name:
        drug_chebi_id = get_onto_id(proper_name, onto='chebi')
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
    # Use the ingredient name if available, otherwise fallback to proper name, trade name, or generic name
    drug_name = ingredient_name_field or proper_name or trade_name or generic_name

    drug_entry = {'name': drug_name}

    if drug_chebi_id:
        drug_entry['chebi_id'] = drug_chebi_id
    elif drugbank_info:
        drug_entry['drugbank_id'] = f"https://go.drugbank.com/drugs/{drugbank_info[0][0]}"

    drug_data['drug'] = [drug_entry]

    # PHASE 6: Process ingredients (if any)
    for ingredient in drug_data.get('ingredients', []):
        ingredient_name = ingredient.get('name', '')
        if ingredient_name:
            print(f"Processing ingredient: '{ingredient_name}'")
            chebi_id = get_onto_id(ingredient_name, onto='chebi')
            if chebi_id:
                ingredient['chebi_id'] = chebi_id
            else:
                drugbank_info = get_drug_info([ingredient_name], drugbank, vocabulary)
                if drugbank_info:
                    ingredient['drugbank_id'] = f"https://go.drugbank.com/drugs/{drugbank_info[0][0]}"
                    # Remove chebi_id if it exists and is null
                    if 'chebi_id' in ingredient and ingredient['chebi_id'] is None:
                        del ingredient['chebi_id']

    # PHASE 7: Process disease-related sections
    for section in ['indications', 'contraindications']:
        text = drug_data.get(section, '')
        if text:
            print(f"\nProcessing section '{section}' with text: '{text}'")
            
            # Find DOID entities within the text using get_onto_id with onto='do' source
            print(f"Calling get_entities.sh for section '{section}' with source 'doid' and text: '{text}'")
            doid_entities_list = get_onto_id(text, onto='do') # Use get_onto_id which now calls get_entities.sh
            print(f"Raw output from get_entities.sh for '{section}' (doid): {doid_entities_list}")

            doid_entities_formatted = []
            if doid_entities_list:
                print(f"Processing {len(doid_entities_list)} DOID entities found")
                # Track unique DOIDs to avoid duplicates
                seen_doids = set()
                
                # doid_entities_list is now a list of [start, end, matched_text, link_or_id]
                for entity_match in doid_entities_list:
                    print(f"Processing entity match: {entity_match}")
                    try:
                        if isinstance(entity_match, list) and len(entity_match) >= 4:
                            # Extract DOID ID from the full URL if present
                            doid_id = entity_match[3]
                            if 'DOID_' in doid_id:
                                doid_id = doid_id.split('DOID_')[-1]
                            
                            # Skip if we've already seen this DOID
                            if doid_id in seen_doids:
                                print(f"Skipping duplicate DOID: {doid_id}")
                                continue
                                
                            seen_doids.add(doid_id)
                            entity_data = {
                                'text': f"{entity_match[2]} (DOID:{doid_id})",  # Format as "text (DOID:id)"
                                'doid_id': f"http://purl.obolibrary.org/obo/DOID_{doid_id}"  # Full DOID URL
                            }
                            doid_entities_formatted.append(entity_data)
                            print(f"Added DOID entity: {entity_data}")
                        else:
                            print(f"Skipping malformed entity match (wrong format): {entity_match}")
                    except Exception as e:
                        print(f"Error processing entity match {entity_match}: {str(e)}")
            else:
                print(f"No DOID entities found for text: '{text}'")

            print(f"Final formatted DOID entities: {doid_entities_formatted}")

            orphanet_entities = []
            # Keep existing ORDO/Orphanet logic as it seems to be working
            disease_entities_from_text = extract_disease_entities(text)
            for disease in disease_entities_from_text:
                orphanet_id = find_disease_in_ontology(disease, disease_terms)
                if orphanet_id:
                    orphanet_entities.append({"disease": disease, "orphanet_id": orphanet_id})
                    
            # Update the section data in drug_data
            # Store original text and lists of found entities
            drug_data[section] = {
                'text': text,  # Keep original text
                'doid_entities': doid_entities_formatted,  # List of found DOID entities
                'orphanet_entities': orphanet_entities  # List of found Orphanet entities (from ORDO)
            }
            print(f"Updated section '{section}' with {len(doid_entities_formatted)} DOID entities and {len(orphanet_entities)} Orphanet entities")

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