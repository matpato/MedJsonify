import os
import json
import configparser
import sys
from concurrent.futures import ThreadPoolExecutor
from NER.src.Utils.utils import *
from NER.src.Utils.utils2mer import *
from NER.src.ner_drugbank import load_drugbank_data, create_vocabulary, get_drug_info
from NER.src.ner_onto import load_ordo, build_disease_dictionary, extract_disease_entities, find_disease_in_ontology

repo_path = os.path.abspath("/opt/airflow/dags/NER/merpy/merpy")
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)
import merpy

# ---------------------------------------------------------------------------------------- #

def get_onto_id(name, onto='chebi', limit=0):
    onto_entities = merpy.get_entities(name, onto)
    print(f"Entities for {name} in {onto}: {onto_entities}")  

    # Verify in there are entities and the first one has more than 3 elements
    if onto_entities and len(onto_entities[0]) > 3 and onto_entities[0][0]:
        return onto_entities[0][3]
    else:
        print(f"No valid entities found for {name} in {onto}") 
        return None

# ---------------------------------------------------------------------------------------- #

def process_drug_data(drug_data, drugbank, vocabulary, disease_terms):
    drug_name = drug_data.get('name', '') or drug_data.get('Proper Name', '')

    drug_chebi_id = get_onto_id(drug_name,onto='chebi') if drug_name else None
    
    drugbank_info = None
    if drug_chebi_id is None:
        drugbank_info = get_drug_info([drug_name], drugbank, vocabulary)
        
        if not drugbank_info and drug_data.get('ingredients'):
            first_ingredient_name = drug_data['ingredients'][0]['name']
            
            drug_name = first_ingredient_name
            
            drug_chebi_id = get_onto_id(drug_name,onto='chebi')
            
            if drug_chebi_id is None:
                drugbank_info = get_drug_info([first_ingredient_name], drugbank, vocabulary)

    drug_entry = {'name': drug_name}
    
    if drug_chebi_id:
        drug_entry['chebi_id'] = drug_chebi_id
    elif drugbank_info:
        drug_entry['drugbank_id'] = drugbank_info[0][0]
    
    drug_data['drug'] = [drug_entry]

    if 'name' in drug_data:
        del drug_data['name']
    if 'Proper Name' in drug_data:
        del drug_data['Proper Name']

    for ingredient in drug_data.get('ingredients', []):
        ingredient['chebi_id'] = get_onto_id(ingredient['name'],onto='chebi') 
        if ingredient['chebi_id'] is None:
            drugbank_info = get_drug_info([ingredient['name']], drugbank, vocabulary)
            if drugbank_info:
                ingredient['drugbank_id'] = drugbank_info[0][0]

    # Process sections using ner_onto's functions for orphanet_id
    for section in ['indications', 'contraindications']:
        text = drug_data.get(section, '')
        if text:
            # Use doid via MER
            doid_id = get_onto_id(text, onto='do')
            
            orphanet_entities = []
            disease_entities = extract_disease_entities(text)
            
            for disease in disease_entities:
                orphanet_id = find_disease_in_ontology(disease, disease_terms)
                if orphanet_id:
                    orphanet_entities.append({"disease": disease, "orphanet_id": orphanet_id})
            
            drug_data[section] = [{
                'text': text,
                'doid_id': doid_id,
                'orphanet_entities': orphanet_entities
            }]

    return drug_data

# ---------------------------------------------------------------------------------------- #

def process_drug_file(file_path, output_dir, drugbank, vocabulary, disease_terms):
    with open(file_path, 'r') as f:
        drug_data = json.load(f)
    
    processed_data = process_drug_data(drug_data, drugbank, vocabulary, disease_terms)

    print(f"Processed data for {file_path}: {processed_data}")

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, os.path.basename(file_path))
    print(f"Saving processed data to: {output_path}")
    
    with open(output_path, 'w') as f_out:
        json.dump(processed_data, f_out, indent=4)

    print(f"File saved: {output_path}")

# ---------------------------------------------------------------------------------------- #

def process_file_in_batch(args):
    file_path, input_dir, output_dir, drugbank, vocabulary, disease_terms = args
    try:
        relative_path = os.path.relpath(file_path, input_dir)
        output_path = os.path.join(output_dir, relative_path)
        output_dir_for_file = os.path.dirname(output_path)

        print(f"Processing file: {file_path}, Output directory: {output_dir_for_file}")
        process_drug_file(file_path, output_dir_for_file, drugbank, vocabulary, disease_terms)
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")

# ---------------------------------------------------------------------------------------- #

def main(active_lexicon, input_dir, output_dir, update, drugbank_file):
    if update == '1':
        update_mer(lexicon=active_lexicon)
    else:
        print("Actualizing ontologies")

    print("Loading ORDO ontology and building disease dictionary...")
    onto = load_ordo()
    disease_terms = build_disease_dictionary(onto)
    print(f"Disease dictionary built with {len(disease_terms)} terms")

    drugbank = load_drugbank_data(drugbank_file)
    vocabulary = create_vocabulary(drugbank)

    files_to_process = []
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith('.json'):
                input_file = os.path.join(root, filename)
                print(f"Adding file to process: {input_file}")
                files_to_process.append((input_file, input_dir, output_dir, drugbank, vocabulary, disease_terms))

    print(f"Total files to process: {len(files_to_process)}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(process_file_in_batch, files_to_process)