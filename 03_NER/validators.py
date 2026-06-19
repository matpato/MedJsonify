import json
import os
from typing import Dict, List

def validate_json_structure(file_path: str) -> bool:
    """Validate JSON file has expected structure"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Check required fields
        required_fields = ['name', 'indications', 'contraindications']
        for field in required_fields:
            if field not in data:
                print(f"Missing required field: {field}")
                return False
        
        return True
    except Exception as e:
        print(f"Validation error: {e}")
        return False

def validate_entity_extraction(file_path: str) -> Dict:
    """Validate that entities were extracted"""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    results = {
        'has_drugbank_id': 'drugbank_id' in str(data),
        'has_chebi_id': 'chebi_id' in str(data),
        'has_doid_entities': 'doid_entities' in str(data),
        'has_orphanet_entities': 'orphanet_entities' in str(data),
    }
    
    return results