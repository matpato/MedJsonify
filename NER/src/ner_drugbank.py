import json
import pandas as pd
import os
import re
from rdkit import Chem
from Levenshtein import jaro_winkler
from functools import lru_cache

def load_drug_data(file_path: str):
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)
    
# ---------------------------------------------------------------------------------------- #

def remove_duplicates(string, delim='; '):
    if not string:
        return ''
    items = string.split(delim)
    unique_items = set(items)
    return delim.join(sorted(unique_items)).strip(delim)

# ---------------------------------------------------------------------------------------- #

def load_drugbank_data(drugbank_file: str):
    drugbank = pd.read_csv(drugbank_file, encoding='ISO-8859-1')
    expected_columns = ['DrugBank ID', 'Common name', 'Synonyms']
    available_columns = drugbank.columns.tolist()
    
    missing_columns = [col for col in expected_columns if col not in available_columns]
    if missing_columns:
        raise ValueError(f"Missing expected columns in DrugBank file: {missing_columns}")
    
    drugbank = drugbank[expected_columns]
    drugbank.rename(columns={'DrugBank ID': 'DRUGBANK_ID', 'Common name': 'GENERIC_NAME', 'Synonyms': 'SYNONYMS'}, inplace=True)
    
    drugbank['SYNONYMS'] = drugbank['SYNONYMS'].fillna('').str.lower().str.split(r';\s*')
    drugbank['GENERIC_NAME'] = drugbank['GENERIC_NAME'].fillna('').str.lower().str.strip()
    
    return drugbank

# ---------------------------------------------------------------------------------------- #

@lru_cache(maxsize=10000)
def calculate_similarity(query, term):
    return jaro_winkler(query, term)

# ---------------------------------------------------------------------------------------- #

def find_closest_drug(query, vocabulary, thresh):
    query = query.lower().strip()
    query = re.sub(r" \(.*?\)", "", query)
    
    best_match = None
    best_score = 0
    
    for term in vocabulary:
        score = calculate_similarity(query, term)
        if score > best_score:
            best_match = term
            best_score = score
    
    print(f"Query: {query}, Best match: {best_match}, Similarity: {best_score}")
    
    return best_match if best_score >= thresh else None

# ---------------------------------------------------------------------------------------- #

def create_vocabulary(drugbank):
    vocabulary = set(drugbank['GENERIC_NAME'])
    for synonyms in drugbank['SYNONYMS']:
        vocabulary.update(synonyms)
    return vocabulary

drug_cache = {} 

# ---------------------------------------------------------------------------------------- #

def get_drug_info(query, drugbank, vocabulary, thresh=0.88):
    results = []
    seen_ids = set()
    
    for q in query:
        q = q.lower().strip()
        
        if q in drug_cache:
            for drug_id, generic_name in drug_cache[q]:
                if drug_id not in seen_ids:
                    results.append((drug_id, generic_name))
                    seen_ids.add(drug_id)
            continue
        
        drug = find_closest_drug(q, vocabulary, thresh)
        
        match_rows = drugbank[drugbank['GENERIC_NAME'] == drug] if drug else pd.DataFrame()
        drug_matches = [(row['DRUGBANK_ID'], row['GENERIC_NAME']) for _, row in match_rows.iterrows()]
        
        drug_cache[q] = drug_matches 
        results.extend(drug_matches)
    
    return results

# ---------------------------------------------------------------------------------------- #

def process_drug_data(data, drugbank, vocabulary):
    name_pattern = re.compile(r" \(.*?\)")
    
    if isinstance(data, list):
        for item in data:
            drug_name = item.get("name", "").strip() or item.get("Proper Name", "").strip()
            if drug_name:
                drug_name = name_pattern.sub("", drug_name)
                item["drugbank_id"] = get_drug_info([drug_name], drugbank, vocabulary)
                print(f"Processing: {drug_name} -> {item['drugbank_id']}")
    elif isinstance(data, dict):
        drug_name = data.get("name", "").strip() or data.get("Proper Name", "").strip()
        if drug_name:
            drug_name = name_pattern.sub("", drug_name)
            data["drugbank_id"] = get_drug_info([drug_name], drugbank, vocabulary)
            print(f"Processing: {drug_name} -> {data['drugbank_id']}")
    
    return data

# ---------------------------------------------------------------------------------------- #

def save_drug_data(data, output_file: str):
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4)

# ---------------------------------------------------------------------------------------- #

def process_folder(input_folder: str, output_folder: str, drugbank_file: str):
    print("Loading data from DrugBank...")
    drugbank = load_drugbank_data(drugbank_file)
    vocabulary = create_vocabulary(drugbank)
    os.makedirs(output_folder, exist_ok=True)
    
    print(f"Processing {len(os.listdir(input_folder))} files...")
    for filename in os.listdir(input_folder):
        if filename.endswith(".json"):
            input_file = os.path.join(input_folder, filename)
            output_file = os.path.join(output_folder, filename)
            
            drug_data = load_drug_data(input_file)
            enriched_data = process_drug_data(drug_data, drugbank, vocabulary)
            save_drug_data(enriched_data, output_file)
    
    print("Done!")