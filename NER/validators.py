import json
import os
from typing import Any, Dict

ENTITY_KEYS = {
    'has_drugbank_id':       'drugbank_id',
    'has_chebi_id':          'chebi_id',
    'has_doid_entities':     'doid_entities',
    'has_orphanet_entities': 'orphanet_entities',
    'has_hp_entities':       'hpo_entities',
}


def _has_value(obj: Any, key: str) -> bool:
    """True if `key` appears anywhere in obj with a non-empty value."""
    if isinstance(obj, dict):
        return any((k == key and v) or _has_value(v, key) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_has_value(x, key) for x in obj)
    return False


def validate_json_structure(file_path: str) -> bool:
    """Validate JSON file has expected structure"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check required fields
        required_fields = ['name', 'indications', 'contraindications']
        for field in required_fields:
            if field not in data:
                print(f"Missing required field: {field}")
                return False

        # After NER, each section should be {'text': ..., '<onto>_entities': [...]}
        for section in ('indications', 'contraindications'):
            value = data[section]
            if isinstance(value, dict) and 'text' not in value:
                print(f"Section '{section}' has no 'text' field")
                return False

        return True
    except Exception as e:
        print(f"Validation error: {e}")
        return False


def validate_entity_extraction(file_path: str) -> Dict[str, bool]:
    """Validate that entities were extracted (non-empty values only)"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return {label: _has_value(data, key) for label, key in ENTITY_KEYS.items()}