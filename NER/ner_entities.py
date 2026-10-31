"""
Named Entities Processing - Core Logic Module 
============================================
Provides core entity identification and drug data processing functions
for use by batch processing scripts.

"""

import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

# ---------------------------------------------------------------------------------------- #
# Configuration
# ---------------------------------------------------------------------------------------- #

# Default paths - can be overridden via environment variables or function parameters
DEFAULT_DATA_DIR = os.environ.get('NER_DATA_DIR', './ontologies/data')
DEFAULT_SCRIPTS_DIR = os.environ.get('NER_SCRIPTS_DIR', './ontologies/scripts')

# ---------------------------------------------------------------------------------------- #
# Entity Identification Functions (Shell-based)
# ---------------------------------------------------------------------------------------- #

def get_onto_id(name: str, 
                onto: str = 'chebi', 
                data_dir: str = DEFAULT_DATA_DIR,
                scripts_dir: str = DEFAULT_SCRIPTS_DIR,
                limit: int = 0,
                all_matches: Optional[bool] = None) -> Optional[List]:
    """
    Get ontology identifier for an entity name using standalone shell scripts.
    
    Args:
        name (str): Entity name to look up
        onto (str): Ontology to search in ('chebi', 'do', 'ordo', 'hp', etc.)
        data_dir (str): Directory containing ontology data files
        scripts_dir (str): Directory containing shell scripts
        limit (int): Minimum number of elements required in entity (unused for now)
        all_matches (bool): Return every match instead of one URI.
                    Defaults to True for 'do' (as before) and False otherwise.
    Returns:
        With all_matches: a list of all matches as lists [start, end, text, uri]
        Otherwise: the first matching URI or None
        
    Examples:
        >>> get_onto_id("asthma", "do")
        [['0', '6', 'asthma', 'http://purl.obolibrary.org/obo/DOID_2841']]
        
        >>> get_onto_id("glucose", "chebi")
        'http://purl.obolibrary.org/obo/CHEBI_17234'
    """
    # Map common ontology names to lexicon names
    onto_source_map = {
        'chebi': 'chebi',
        'do': 'doid',
        'ordo': 'ordo',
        'hp': 'hpo'
    }
    
    lexicon_name = onto_source_map.get(onto, onto)
    extract_script = Path(scripts_dir) / "extract_entities.sh"
    
    # Check if script exists
    if not extract_script.exists():
        print(f"ERROR: Extract script not found at {extract_script}")
        return None
    
    # Make script executable
    os.chmod(extract_script, 0o755)
    
    # Build command
    command = [str(extract_script), name, lexicon_name, str(data_dir)]
    
    print(f"Executing: {' '.join(command)}")
    
    try:
        # Execute shell script
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(scripts_dir).parent)
        )
        
        # Debug output
        if result.stderr:
            print(f"Script stderr: {result.stderr}")
        
        # Parse output
        entities = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('\t')
            if len(parts) >= 3:
                # Format: START\tEND\tTEXT\t[URI]
                entity = [parts[0], parts[1], parts[2]]
                if len(parts) > 3:
                    entity.append(parts[3])
                entities.append(entity)
        
        print(f"Found {len(entities)} entities for '{name}' in {lexicon_name}: {entities}")
        
        # For text annotation (DOID by default), return all matches
        if all_matches is None:
            all_matches = (onto == 'do')
        if all_matches:
            return entities if entities else None
        
        # For other ontologies, return first URI or None
        if entities:
            # Try to find exact match first
            name_lower = name.lower().strip()
            for entity in entities:
                if entity[2].lower().strip() == name_lower:
                    return entity[3] if len(entity) > 3 else None
            
            # Otherwise return first match's URI
            return entities[0][3] if len(entities[0]) > 3 else None
        
        return None
    
    except subprocess.TimeoutExpired:
        print(f"ERROR: Script execution timed out after 60 seconds")
        return None
    except Exception as e:
        print(f"ERROR executing script: {e}")
        return None

# ---------------------------------------------------------------------------------------- #
# Disease Entity Extraction
# ---------------------------------------------------------------------------------------- #

def extract_disease_entities(text: str, 
                            data_dir: str = DEFAULT_DATA_DIR,
                            scripts_dir: str = DEFAULT_SCRIPTS_DIR) -> List[str]:
    """
    Extract disease entities from text using DOID ontology.
    
    Args:
        text (str): Text to extract diseases from
        data_dir (str): Directory containing ontology data
        scripts_dir (str): Directory containing shell scripts
        
    Returns:
        List of unique disease names found in text
    """
    if not text:
        return []
    
    # Get DOID entities
    entities = get_onto_id(text, onto='do', data_dir=data_dir, scripts_dir=scripts_dir)
    
    if not entities:
        return []
    
    # Extract unique disease names
    diseases = set()
    for entity in entities:
        if len(entity) >= 3:
            diseases.add(entity[2])  # entity[2] is the matched text
    
    return list(diseases)

# ---------------------------------------------------------------------------------------- #
# Orphanet/ORDO Functions
# ---------------------------------------------------------------------------------------- #

def find_disease_in_ontology(disease_name: str, 
                            disease_terms: Dict[str, str],
                            data_dir: str = DEFAULT_DATA_DIR,
                            scripts_dir: str = DEFAULT_SCRIPTS_DIR) -> Optional[str]:
    """
    Find disease in Orphanet ontology.
    
    Args:
        disease_name (str): Disease name to look up
        disease_terms (dict): Dictionary mapping disease names to Orphanet IDs
        data_dir (str): Directory containing ontology data
        scripts_dir (str): Directory containing shell scripts
        
    Returns:
        Orphanet URI if found, None otherwise
    """
    # First try direct lookup in disease_terms dictionary
    disease_lower = disease_name.lower().strip()
    
    if disease_lower in disease_terms:
        return disease_terms[disease_lower]
    
    # Try shell script extraction
    orphanet_id = get_onto_id(disease_name, onto='ordo', 
                              data_dir=data_dir, scripts_dir=scripts_dir)
    
    return orphanet_id

# ---------------------------------------------------------------------------------------- #
# Drug Data Processing Functions 
# ---------------------------------------------------------------------------------------- #

def process_drug_data(drug_data: Dict, 
                     drugbank, 
                     vocabulary,
                     disease_terms: Dict,
                     data_dir: str = DEFAULT_DATA_DIR,
                     scripts_dir: str = DEFAULT_SCRIPTS_DIR) -> Dict:
    """
    Process a single drug data object, enriching the drug and its ingredients
    with identifiers: DrugBank first (by UNII code when the source gives one,
    then by name), ChEBI only when DrugBank has no match. Each entry gets
    'match' = unii / exact / fuzzy / chebi, so the matching can be reported.
    Diseases are added afterwards by process_disease_data.

    Args:
        drug_data (dict): Drug data to process
        drugbank: DrugBank DataFrame
        vocabulary: Drug vocabulary set
        disease_terms (dict): Disease terms dictionary (not used here; kept so
            existing callers keep working)
        data_dir (str): Directory containing ontology data
        scripts_dir (str): Directory containing shell scripts
        
    Returns:
        Enriched drug data dictionary
    """
    try:
        import ner_drugbank as _db
    except ImportError:
        # Try absolute import if relative fails
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import ner_drugbank as _db

    def drugbank_lookup(name='', unii=None):
        """(DrugBank hits, match type) -- UNII first, then exact name, then fuzzy."""
        if hasattr(_db, 'find_drug'):
            return _db.find_drug(name, drugbank, vocabulary, unii=unii)
        hits = _db.get_drug_info([name], drugbank, vocabulary) if name else []   # older ner_drugbank
        return hits, ('name' if hits else None)

    def drugbank_url(hits):
        return f"https://go.drugbank.com/drugs/{hits[0][0]}"

    def as_text(value):
        """A name field as text: labels with several products give a list
        (the first name is used); numbers and None are handled too."""
        if isinstance(value, list):
            value = next((v for v in value if isinstance(v, str) and v.strip()), '')
        return value.strip() if isinstance(value, str) else ''

    print(f"Processing drug data for: {as_text(drug_data.get('name')) or as_text(drug_data.get('Proper Name')) or 'Unknown Drug'}")
    
    # PHASE 1: Extract drug names
    trade_name = as_text(drug_data.get('Trade_Name'))
    proper_name = as_text(drug_data.get('Proper Name'))
    generic_name = as_text(drug_data.get('name'))
    ingredient_name_field = as_text(drug_data.get('Ingredient'))

    if not trade_name and not proper_name and not generic_name:
        return drug_data

    active_ingredients = [
        ingredient for ingredient in drug_data.get('ingredients', [])
        if (ingredient.get('class_code') or '').upper().startswith('ACT')
    ]
    first_active = active_ingredients[0] if active_ingredients else {}
    first_active_name = as_text(first_active.get('name'))

    # Names to try, most specific first; the first active ingredient is the last resort
    candidate_names = [n for n in (ingredient_name_field, trade_name, proper_name,
                                   generic_name, first_active_name) if n]

    # PHASE 2: DrugBank lookup (primary source): the first active ingredient's
    # UNII code (DailyMed) first, then the names
    drugbank_info, match_type = [], None
    if first_active.get('code'):
        drugbank_info, match_type = drugbank_lookup(unii=first_active.get('code'))
    if not drugbank_info:
        for candidate in candidate_names:
            drugbank_info, match_type = drugbank_lookup(candidate)
            if drugbank_info:
                break

    # PHASE 3: ChEBI lookup, only if DrugBank found nothing
    drug_chebi_id = None
    if not drugbank_info:
        for candidate in candidate_names:
            drug_chebi_id = get_onto_id(candidate, onto='chebi',
                                        data_dir=data_dir, scripts_dir=scripts_dir)
            if drug_chebi_id:
                match_type = 'chebi'
                break

    # PHASE 4: Build drug entry with identifier
    drug_name = ingredient_name_field or proper_name or trade_name or generic_name
    drug_entry = {'name': drug_name}

    if drugbank_info:
        drug_entry['drugbank_id'] = drugbank_url(drugbank_info)
    elif drug_chebi_id:
        drug_entry['chebi_id'] = drug_chebi_id
    if match_type:
        drug_entry['match'] = match_type        # unii / exact / fuzzy / chebi

    drug_data['drug'] = [drug_entry]

    # PHASE 5: Process ingredients (if any): DrugBank (UNII, then name) first,
    # ChEBI as fallback
    for ingredient in drug_data.get('ingredients', []):
        ingredient_name = as_text(ingredient.get('name'))
        if ingredient_name:
            print(f"Processing ingredient: '{ingredient_name}'")
            info, how = drugbank_lookup(ingredient_name, unii=ingredient.get('code'))
            if info:
                ingredient['drugbank_id'] = drugbank_url(info)
                ingredient['match'] = how
            else:
                chebi_id = get_onto_id(ingredient_name, onto='chebi',
                                       data_dir=data_dir, scripts_dir=scripts_dir)
                if chebi_id:
                    ingredient['chebi_id'] = chebi_id
                    ingredient['match'] = 'chebi'
            # Remove chebi_id if it exists and is null
            if 'chebi_id' in ingredient and ingredient['chebi_id'] is None:
                del ingredient['chebi_id']

    return drug_data


# ---------------------------------------------------------------------------------------- #
# Disease Processing Functions
# ---------------------------------------------------------------------------------------- #

# HPO terms allowed as diseases: those under "Phenotypic abnormality" (HP:0000118).
# The list is written by the ontology step (fetch_ontologies.py) as
# <data_dir>/hpo_phenotypes.txt; other HPO branches (clinical modifiers such as
# 'chronic', 'severe', 'progressive', mode of inheritance, frequency...) are not diseases.
_HPO_PHENOTYPES = {}
_HPO_LOCK = __import__('threading').Lock()


def _hpo_phenotypes(data_dir: str):
    """Set of allowed HPO numbers ('0002206'), or None if the list is missing."""
    with _HPO_LOCK:
        if data_dir not in _HPO_PHENOTYPES:
            path = Path(data_dir) / 'hpo_phenotypes.txt'
            if path.exists():
                ids = {line.strip().split(':')[-1].split('_')[-1]
                       for line in path.read_text(encoding='utf-8').splitlines() if line.strip()}
                print(f"HPO: {len(ids)} phenotype terms allowed (from {path.name})")
                _HPO_PHENOTYPES[data_dir] = ids
            else:
                print(f"WARNING: {path} not found -- all HPO terms are kept, including "
                      "clinical modifiers such as 'chronic' or 'severe'. "
                      "Run the ontology step to create it.")
                _HPO_PHENOTYPES[data_dir] = None
        return _HPO_PHENOTYPES[data_dir]


def process_disease_data(drug_data: Dict,
                         data_dir: str = DEFAULT_DATA_DIR,
                         scripts_dir: str = DEFAULT_SCRIPTS_DIR) -> Dict:
    """
    Add disease entities to the indications and contraindications of a drug
    data object, after process_drug_data.

    Diseases are searched in the full section text with DOID, then ORDO, then
    HPO. Rules:
      - one link per mention: a text span already linked (by an earlier
        ontology, or by a longer match of the same ontology) is not linked
        again, so 'interstitial lung disease' does not also give 'lung disease';
      - within an ontology, longer matches win over shorter ones inside them;
      - only terms of the ontology itself are kept (hp.owl also contains
        UBERON, ChEBI, PATO... classes);
      - HPO: only terms under Phenotypic abnormality (see _hpo_phenotypes).
    Sections already processed (no longer plain text) are left as they are,
    so calling this twice is harmless.

    Args:
        drug_data (dict): Drug data, as returned by process_drug_data
        data_dir (str): Directory containing ontology data
        scripts_dir (str): Directory containing shell scripts

    Returns:
        Drug data with each section as {'text', 'doid_entities',
        'orphanet_entities', 'hpo_entities'}
    """
    # For each ontology: (onto for get_onto_id, prefix in the mention text,
    # separator in the URI, list key in the output, ID key in each entity)
    disease_ontologies = (
        ('do',   'DOID',  'DOID_',     'doid_entities',     'doid_id'),
        ('ordo', 'ORPHA', 'Orphanet_', 'orphanet_entities', 'orphanet_id'),
        ('hp',   'HP',    'HP_',       'hpo_entities',      'hpo_id'),
    )
    hpo_allowed = _hpo_phenotypes(data_dir)

    for section in ['indications', 'contraindications']:
        text = drug_data.get(section, '')
        if not text or not isinstance(text, str):
            continue
        print(f"\nProcessing section '{section}'")

        section_data = {'text': text}
        taken_spans = []     # text spans already linked
        taken_texts = set()  # used when the script gives no offsets

        for onto, prefix, uri_sep, list_key, id_key in disease_ontologies:
            # all_matches=True: every mention in the text, not just one URI
            matches = get_onto_id(text, onto=onto, data_dir=data_dir,
                                  scripts_dir=scripts_dir, all_matches=True) or []
            print(f"Raw {prefix} entities for '{section}': {matches}")

            # Valid matches of this ontology, with their text span
            candidates = []
            for match in matches:
                if not isinstance(match, list) or len(match) < 4 or not match[3]:
                    continue
                mention, uri = match[2], match[3]
                # Keep only terms of this ontology: hp.owl also contains classes
                # imported from ChEBI, UBERON, PATO, MPATH... (e.g. 'lung', 'inhibitor')
                if uri_sep not in uri:
                    continue
                number = uri.split(uri_sep)[-1]
                if onto == 'hp' and hpo_allowed is not None and number not in hpo_allowed:
                    continue          # not a phenotype ('chronic', 'severe', ...)
                try:
                    span = (int(match[0]), int(match[1]))
                except (ValueError, TypeError):
                    span = None
                candidates.append((span, mention, uri, number))

            # Longest matches first, so a phrase wins over the shorter phrases inside it
            candidates.sort(key=lambda c: (c[0] is None,
                                           -(c[0][1] - c[0][0]) if c[0] else -len(c[1]),
                                           c[0][0] if c[0] else 0))

            entities, seen_ids = [], set()
            for span, mention, uri, number in candidates:
                # Skip mentions already linked (earlier ontology or longer match)
                if span is not None and any(span[0] < e and s < span[1] for s, e in taken_spans):
                    continue
                if span is None and mention.lower() in taken_texts:
                    continue
                if number in seen_ids:
                    print(f"Skipping duplicate {prefix}: {number}")
                    continue
                seen_ids.add(number)
                if span is not None:
                    taken_spans.append(span)
                taken_texts.add(mention.lower())

                if onto == 'do':   # keep the DOID URI format used so far
                    uri = f"http://purl.obolibrary.org/obo/DOID_{number}"
                entity = {'text': f"{mention} ({prefix}:{number})", id_key: uri}
                if onto == 'ordo':
                    entity['disease'] = mention   # old key, kept for compatibility
                entities.append(entity)

            section_data[list_key] = entities

        drug_data[section] = section_data
        print(f"Updated section '{section}' with "
              + ", ".join(f"{len(section_data[k])} {p}" for _, p, _, k, _ in disease_ontologies)
              + " entities")

    return drug_data