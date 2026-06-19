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
                limit: int = 0) -> Optional[List]:
    """
    Get ontology identifier for an entity name using standalone shell scripts.
    
    Args:
        name (str): Entity name to look up
        onto (str): Ontology to search in ('chebi', 'do', 'ordo', 'hp', etc.)
        data_dir (str): Directory containing ontology data files
        scripts_dir (str): Directory containing shell scripts
        limit (int): Minimum number of elements required in entity (unused for now)
        
    Returns:
        For 'do' (DOID): Returns a list of all matches as lists [start, end, text, uri]
        For other ontologies: Returns the first matching URI or None
        
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
        
        # For DOID, return all matches
        if onto == 'do':
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
    Process a single drug data object, enriching it with ontology identifiers.
    
    Args:
        drug_data (dict): Drug data to process
        drugbank: DrugBank DataFrame
        vocabulary: Drug vocabulary set
        disease_terms (dict): Disease terms dictionary
        data_dir (str): Directory containing ontology data
        scripts_dir (str): Directory containing shell scripts
        
    Returns:
        Enriched drug data dictionary
    """
    try:
        from ner_drugbank import get_drug_info  
    except ImportError:
    # Try absolute import if relative fails
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from ner_drugbank import get_drug_info
    
    print(f"Processing drug data for: {drug_data.get('name', drug_data.get('Proper Name', 'Unknown Drug'))}")
    
    # PHASE 1: Extract drug names
    trade_name = drug_data.get('Trade_Name', '').strip()
    proper_name = drug_data.get('Proper Name', '').strip()
    generic_name = drug_data.get('name', '').strip()
    ingredient_name_field = drug_data.get('Ingredient', '').strip()

    if not trade_name and not proper_name and not generic_name:
        return drug_data

    # PHASE 2: Try to get ChEBI ID for drug
    drug_chebi_id = None
    
    # Try Ingredient name first as it's more likely to match ChEBI
    if ingredient_name_field:
        drug_chebi_id = get_onto_id(ingredient_name_field, onto='chebi', 
                                    data_dir=data_dir, scripts_dir=scripts_dir)
    
    # Then try other names if no match found
    if drug_chebi_id is None and trade_name:
        drug_chebi_id = get_onto_id(trade_name, onto='chebi',
                                    data_dir=data_dir, scripts_dir=scripts_dir)
    if drug_chebi_id is None and proper_name:
        drug_chebi_id = get_onto_id(proper_name, onto='chebi',
                                    data_dir=data_dir, scripts_dir=scripts_dir)
    if drug_chebi_id is None and generic_name:
        drug_chebi_id = get_onto_id(generic_name, onto='chebi',
                                    data_dir=data_dir, scripts_dir=scripts_dir)

    # PHASE 3: If no ChEBI ID, try DrugBank lookup
    drugbank_info = None
    if drug_chebi_id is None:
        if trade_name:
            drugbank_info = get_drug_info([trade_name], drugbank, vocabulary)
        if not drugbank_info and proper_name:
            drugbank_info = get_drug_info([proper_name], drugbank, vocabulary)
        if not drugbank_info and generic_name:
            drugbank_info = get_drug_info([generic_name], drugbank, vocabulary)
        
        # PHASE 4: If still no match and ingredients are available, try first ingredient
        if not drugbank_info and drug_data.get('ingredients'):
            first_ingredient = drug_data['ingredients'][0]
            first_ingredient_name = first_ingredient.get('name', '')
            if first_ingredient_name:
                drug_chebi_id = get_onto_id(first_ingredient_name, onto='chebi',
                                           data_dir=data_dir, scripts_dir=scripts_dir)
                if drug_chebi_id is None:
                    drugbank_info = get_drug_info([first_ingredient_name], drugbank, vocabulary)

    # PHASE 5: Build drug entry with identifier
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
            chebi_id = get_onto_id(ingredient_name, onto='chebi',
                                  data_dir=data_dir, scripts_dir=scripts_dir)
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
            
            # Find DOID entities within the text
            print(f"Extracting DOID entities for section '{section}'")
            doid_entities_list = get_onto_id(text, onto='do', 
                                            data_dir=data_dir, scripts_dir=scripts_dir)
            print(f"Raw DOID entities for '{section}': {doid_entities_list}")

            doid_entities_formatted = []
            if doid_entities_list:
                print(f"Processing {len(doid_entities_list)} DOID entities found")
                seen_doids = set()
                
                for entity_match in doid_entities_list:
                    print(f"Processing entity match: {entity_match}")
                    try:
                        if isinstance(entity_match, list) and len(entity_match) >= 4:
                            # Extract DOID ID from the full URL
                            doid_id = entity_match[3]
                            if 'DOID_' in doid_id:
                                doid_id = doid_id.split('DOID_')[-1]
                            
                            # Skip duplicates
                            if doid_id in seen_doids:
                                print(f"Skipping duplicate DOID: {doid_id}")
                                continue
                            
                            seen_doids.add(doid_id)
                            entity_data = {
                                'text': f"{entity_match[2]} (DOID:{doid_id})",
                                'doid_id': f"http://purl.obolibrary.org/obo/DOID_{doid_id}"
                            }
                            doid_entities_formatted.append(entity_data)
                            print(f"Added DOID entity: {entity_data}")
                    except Exception as e:
                        print(f"Error processing entity match {entity_match}: {str(e)}")
            else:
                print(f"No DOID entities found for text: '{text}'")

            print(f"Final formatted DOID entities: {doid_entities_formatted}")

            # Extract and process Orphanet entities
            orphanet_entities = []
            disease_entities_from_text = extract_disease_entities(text, data_dir, scripts_dir)
            for disease in disease_entities_from_text:
                orphanet_id = find_disease_in_ontology(disease, disease_terms,
                                                       data_dir, scripts_dir)
                if orphanet_id:
                    orphanet_entities.append({"disease": disease, "orphanet_id": orphanet_id})
            
            # Update the section data
            drug_data[section] = {
                'text': text,
                'doid_entities': doid_entities_formatted,
                'orphanet_entities': orphanet_entities
            }
            print(f"Updated section '{section}' with {len(doid_entities_formatted)} DOID entities and {len(orphanet_entities)} Orphanet entities")

    return drug_data