import os
import json
import configparser
from concurrent.futures import ThreadPoolExecutor
from NER.src.Utils.utils import *
from NER.src.Utils.utils2mer import *
from NER.src.ner_drugbank import load_drugbank_data, create_vocabulary, get_drug_info

repo_path = os.path.abspath("/opt/airflow/dags/NER/merpy/merpy")
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)
import merpy

# ---------------------------------------------------------------------------------------- #

def get_onto_id(name, onto='chebi', limit=0):
    # Obter entidades da ontologia
    onto_entities = merpy.get_entities(name, onto)
    print(f"Entities for {name} in {onto}: {onto_entities}")  # Log para depuração

    # Verificar se há entidades e se a primeira sublista tem pelo menos 4 elementos
    if onto_entities and len(onto_entities[0]) > 3 and onto_entities[0][0]:
        return onto_entities[0][3]
    else:
        print(f"No valid entities found for {name} in {onto}")  # Log para depuração
        return None

# ---------------------------------------------------------------------------------------- #

def process_drug_data(drug_data, drugbank, vocabulary):
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

    for section in ['indications', 'contraindications']:
        text = drug_data.get(section, '')
        if text:
            drug_data[section] = [{
                'text': text,
                'doid_id': get_onto_id(text,onto='do'),
                'orphanet_id': get_onto_id(text,onto='ordo')  
            }]

    return drug_data

# ---------------------------------------------------------------------------------------- #

def process_drug_file(file_path, output_dir, drugbank, vocabulary):
    with open(file_path, 'r') as f:
        drug_data = json.load(f)
    
    processed_data = process_drug_data(drug_data, drugbank, vocabulary)

    print(f"Processed data for {file_path}: {processed_data}")

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, os.path.basename(file_path))
    print(f"Saving processed data to: {output_path}")
    
    with open(output_path, 'w') as f_out:
        json.dump(processed_data, f_out, indent=4)

    print(f"File saved: {output_path}")

# ---------------------------------------------------------------------------------------- #

def process_file_in_batch(args):
    file_path, input_dir, output_dir, drugbank, vocabulary = args
    try:
        relative_path = os.path.relpath(file_path, input_dir)
        output_path = os.path.join(output_dir, relative_path)
        output_dir_for_file = os.path.dirname(output_path)

        print(f"Processing file: {file_path}, Output directory: {output_dir_for_file}")
        process_drug_file(file_path, output_dir_for_file, drugbank, vocabulary)
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")

# ---------------------------------------------------------------------------------------- #

def main(active_lexicon, input_dir, output_dir, update, drugbank_file):
    if update == '1':
        update_mer(lexicon=active_lexicon)
    else:
        print("Actualizing ontologies")

    drugbank = load_drugbank_data(drugbank_file)
    vocabulary = create_vocabulary(drugbank)

    files_to_process = []
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith('.json'):
                input_file = os.path.join(root, filename)
                print(f"Adding file to process: {input_file}")
                files_to_process.append((input_file, input_dir, output_dir, drugbank, vocabulary))

    print(f"Total files to process: {len(files_to_process)}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(process_file_in_batch, files_to_process)

# ---------------------------------------------------------------------------------------- #

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('/opt/airflow/dags/NER/src/config.ini')
    active_lexicon = config['ONTO']['active_lexicons'].replace(' ', '').split(',')
    input_dir, output_dir = create_entities_folder(src=config['PATH']['path_to_original_json'])
    update = config['ONTO'].get('update')
    drugbank_file = config['PATH']['path_to_drugbank_csv']
    main(active_lexicon, input_dir, output_dir, update, drugbank_file)