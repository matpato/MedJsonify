"""
DrugBank NER Module
===================
Objective: Enrich pharmaceutical data by matching drug names with DrugBank IDs.

This module:
1. Loads the DrugBank vocabulary (DrugBank ID, Common name, Synonyms, UNII)
2. Builds look-up tables of names (common names AND synonyms) and UNII codes
3. Matches a drug in this order, stopping at the first hit:
     a. UNII code (exact; DailyMed gives each ingredient its UNII)
     b. exact name or synonym (after normalisation), also without salt words
        ("DESIPRAMINE HYDROCHLORIDE" -> "desipramine": DailyMed often names the salt)
     c. fuzzy name match (Jaro-Winkler >= threshold, default 0.88)
4. Returns (DrugBank ID, common name) pairs; find_drug() also says which of
   a/b/c was used, so the match type can be reported.

The purpose is to standardize drug references across datasets by linking them to authoritative
identifiers, enabling more accurate data integration and analysis in pharmaceutical applications.
"""

import io
import json
import os
import re
import threading
from typing import Dict, List, Optional, Tuple

import pandas as pd
from Levenshtein import jaro_winkler

# ---------------------------------------------------------------------------------------- #
# File Loading Functions
# ---------------------------------------------------------------------------------------- #

def load_drug_data(file_path: str):
    """Load drug data from a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)


def remove_duplicates(string, delim='; '):
    """Remove duplicate items from a delimited string."""
    if not string:
        return ''
    items = string.split(delim)
    return delim.join(sorted(set(items))).strip(delim)

# ---------------------------------------------------------------------------------------- #
# DrugBank Data Processing
# ---------------------------------------------------------------------------------------- #

# Salt / form words: "DESIPRAMINE HYDROCHLORIDE" -> "desipramine". DailyMed names
# (and UNII codes) are often those of the salt, DrugBank's of the parent drug.
SALT_WORDS = {
    'hydrochloride', 'dihydrochloride', 'hydrobromide', 'hcl', 'sodium', 'disodium',
    'potassium', 'calcium', 'magnesium', 'zinc', 'lithium', 'sulfate', 'sulphate',
    'bisulfate', 'phosphate', 'diphosphate', 'acetate', 'diacetate', 'citrate',
    'maleate', 'fumarate', 'hemifumarate', 'tartrate', 'bitartrate', 'succinate',
    'mesylate', 'mesilate', 'besylate', 'besilate', 'esylate', 'tosylate', 'lactate',
    'gluconate', 'nitrate', 'oxalate', 'bromide', 'chloride', 'iodide', 'malate',
    'monohydrate', 'dihydrate', 'trihydrate', 'hemihydrate', 'sesquihydrate',
    'anhydrous', 'hyclate', 'pamoate', 'stearate', 'propionate', 'dipropionate',
    'valerate', 'butyrate', 'benzoate', 'carbonate', 'trometamol', 'tromethamine',
    'meglumine', 'decanoate', 'enanthate', 'cypionate',
}

# DrugBank separates synonyms with " | " (older exports used "; ")
_SYNONYM_SPLIT = re.compile(r'\s*\|\s*|;\s*')


def normalize_name(name) -> str:
    """Lower case, without text in parentheses, single spaces."""
    if not isinstance(name, str):
        return ''
    name = name.lower().strip()
    name = re.sub(r'\s*\(.*?\)', '', name)
    return re.sub(r'\s+', ' ', name).strip()


def strip_salt(name: str) -> str:
    """'desipramine hydrochloride' -> 'desipramine' (trailing salt/form words only)."""
    words = name.split()
    while len(words) > 1 and words[-1] in SALT_WORDS:
        words.pop()
    return ' '.join(words)


def load_drugbank_data(drugbank_file: str):
    """
    Load and preprocess DrugBank data from the vocabulary CSV.

    Returns:
        pandas.DataFrame with DRUGBANK_ID, GENERIC_NAME, SYNONYMS (list) and,
        if the file has it, UNII.
    """
    raw = open(drugbank_file, 'rb').read()
    try:
        text = raw.decode('utf-8-sig')            # DrugBank files are UTF-8
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
    drugbank = pd.read_csv(io.StringIO(text), dtype=str)

    expected_columns = ['DrugBank ID', 'Common name', 'Synonyms']
    missing_columns = [col for col in expected_columns if col not in drugbank.columns]
    if missing_columns:
        raise ValueError(f"Missing expected columns in DrugBank file: {missing_columns}")

    columns = expected_columns + (['UNII'] if 'UNII' in drugbank.columns else [])
    drugbank = drugbank[columns].rename(columns={
        'DrugBank ID': 'DRUGBANK_ID',
        'Common name': 'GENERIC_NAME',
        'Synonyms': 'SYNONYMS',
    })

    drugbank['SYNONYMS'] = drugbank['SYNONYMS'].fillna('').apply(
        lambda s: [normalize_name(x) for x in _SYNONYM_SPLIT.split(s) if normalize_name(x)])
    drugbank['GENERIC_NAME'] = drugbank['GENERIC_NAME'].fillna('').apply(normalize_name)
    if 'UNII' in drugbank.columns:
        drugbank['UNII'] = drugbank['UNII'].fillna('').str.strip().str.upper()
    return drugbank

# ---------------------------------------------------------------------------------------- #
# Look-up tables (built once per DrugBank table, shared by all threads)
# ---------------------------------------------------------------------------------------- #

_INDEX_LOCK = threading.Lock()
_INDEXES: Dict[int, dict] = {}


def _indexes(drugbank) -> dict:
    """name -> [(id, common name)], unii -> [(id, common name)], generic names list."""
    key = id(drugbank)
    with _INDEX_LOCK:
        if key not in _INDEXES:
            by_name, by_unii = {}, {}
            for row in drugbank.itertuples(index=False):
                entry = (row.DRUGBANK_ID, row.GENERIC_NAME)
                # common name first, so it wins over a synonym shared by several drugs
                if row.GENERIC_NAME:
                    by_name.setdefault(row.GENERIC_NAME, []).insert(0, entry)
                for syn in row.SYNONYMS:
                    if entry not in by_name.setdefault(syn, []):
                        by_name[syn].append(entry)
                unii = getattr(row, 'UNII', '')
                if unii:
                    by_unii.setdefault(unii, []).append(entry)
            _INDEXES[key] = {'name': by_name, 'unii': by_unii, 'names': list(by_name)}
            print(f"DrugBank index: {len(by_name)} names and synonyms, {len(by_unii)} UNII codes")
        return _INDEXES[key]

# ---------------------------------------------------------------------------------------- #
# String Similarity Functions
# ---------------------------------------------------------------------------------------- #

def calculate_similarity(query, term):
    """Jaro-Winkler similarity between two strings (0-1)."""
    return jaro_winkler(query, term)


def find_closest_drug(query, vocabulary, thresh):
    """
    Closest drug name in the vocabulary (Jaro-Winkler), or None if below thresh.
    An exact match is returned at once without scanning the vocabulary.
    """
    query = normalize_name(query)
    if not query:
        return None
    if query in vocabulary:
        return query
    best_match, best_score = None, 0.0
    for term in vocabulary:
        score = jaro_winkler(query, term)
        if score > best_score:
            best_match, best_score = term, score
    print(f"Query: {query}, Best match: {best_match}, Similarity: {best_score:.3f}")
    return best_match if best_score >= thresh else None

# ---------------------------------------------------------------------------------------- #
# Vocabulary and Drug Information Functions
# ---------------------------------------------------------------------------------------- #

def create_vocabulary(drugbank):
    """Set of all drug names and synonyms (normalised)."""
    vocabulary = set(n for n in drugbank['GENERIC_NAME'] if n)
    for synonyms in drugbank['SYNONYMS']:
        vocabulary.update(synonyms)
    return vocabulary


# Cache of name look-ups: normalised query -> (results, method)
drug_cache: Dict[str, Tuple[list, Optional[str]]] = {}
_CACHE_LOCK = threading.Lock()


def find_drug(name: str, drugbank, vocabulary=None, thresh: float = 0.88,
              unii: Optional[str] = None) -> Tuple[List[Tuple[str, str]], Optional[str]]:
    """
    DrugBank matches for one drug, and how they were found.

    Returns:
        ([(DrugBank ID, common name), ...], method) with method 'unii',
        'exact', 'exact_parent' (exact after removing salt words), 'fuzzy',
        or None when nothing matched.
    """
    idx = _indexes(drugbank)

    # a. UNII code: exact and unambiguous
    if unii:
        hits = idx['unii'].get(str(unii).strip().upper())
        if hits:
            return list(hits), 'unii'

    q = normalize_name(name)
    if not q:
        return [], None
    with _CACHE_LOCK:
        if q in drug_cache:
            return drug_cache[q]

    # b. exact name or synonym, then without salt words ("... hydrochloride")
    base = strip_salt(q)
    if q in idx['name']:
        result = (list(idx['name'][q]), 'exact')
    elif base != q and base in idx['name']:
        result = (list(idx['name'][base]), 'exact_parent')
    else:
        # c. fuzzy match over all names and synonyms
        match = find_closest_drug(q, vocabulary or idx['names'], thresh)
        hits = idx['name'].get(match, []) if match else []
        result = (list(hits), 'fuzzy' if hits else None)

    with _CACHE_LOCK:
        drug_cache[q] = result
    return result


def get_drug_info(query, drugbank, vocabulary, thresh=0.88):
    """
    DrugBank IDs for a list of drug names (unchanged interface).

    Returns:
        list of (DrugBank ID, common name), without duplicates.
    """
    results, seen_ids = [], set()
    for q in query:
        hits, _ = find_drug(q, drugbank, vocabulary, thresh)
        for drug_id, generic_name in hits:
            if drug_id not in seen_ids:
                results.append((drug_id, generic_name))
                seen_ids.add(drug_id)
    return results


def get_drug_by_unii(unii, drugbank):
    """DrugBank IDs for a UNII code (e.g. the ingredient code in DailyMed), or []."""
    hits, method = find_drug('', drugbank, unii=unii)
    return hits if method == 'unii' else []

# ---------------------------------------------------------------------------------------- #
# Data Processing Functions
# ---------------------------------------------------------------------------------------- #

def process_drug_data(data, drugbank, vocabulary):
    """Add DrugBank IDs to a drug item or a list of items (by name)."""
    items = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    for item in items:
        drug_name = (item.get("name") or "").strip() or (item.get("Proper Name") or "").strip()
        if drug_name:
            item["drugbank_id"] = get_drug_info([drug_name], drugbank, vocabulary)
            print(f"Processing: {drug_name} -> {item['drugbank_id']}")
    return data


def save_drug_data(data, output_file: str):
    """Save processed drug data to a JSON file."""
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

# ---------------------------------------------------------------------------------------- #
# Main Processing Function
# ---------------------------------------------------------------------------------------- #

def process_folder(input_folder: str, output_folder: str, drugbank_file: str):
    """Add DrugBank IDs to every JSON file in a folder."""
    print("Loading data from DrugBank...")
    drugbank = load_drugbank_data(drugbank_file)
    vocabulary = create_vocabulary(drugbank)
    os.makedirs(output_folder, exist_ok=True)
    files = [f for f in os.listdir(input_folder) if f.endswith(".json")]
    print(f"Processing {len(files)} files...")
    for filename in files:
        data = load_drug_data(os.path.join(input_folder, filename))
        save_drug_data(process_drug_data(data, drugbank, vocabulary),
                       os.path.join(output_folder, filename))
    print("Processing complete!")