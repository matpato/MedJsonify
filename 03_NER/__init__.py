"""
NER Package - Biomedical Named Entity Recognition

This package provides tools for extracting biomedical entities from text using
ontologies and shell-based processing.
"""

# Make key classes and functions available at package level
from .standalone_bioner import StandaloneBioNER, COMMON_ONTOLOGIES
from .ner_entities import (
    get_onto_id,
    extract_disease_entities,
    find_disease_in_ontology,
    process_drug_data
)
from .ner_drugbank import (
    load_drugbank_data,
    create_vocabulary,
    get_drug_info
)
from .Biomedical_preprocessing import BiomedicalPreprocessor
from .download_vocabulary import download_and_extract_zip

__all__ = [
    'StandaloneBioNER',
    'COMMON_ONTOLOGIES',
    'get_onto_id',
    'extract_disease_entities',
    'find_disease_in_ontology',
    'process_drug_data',
    'load_drugbank_data',
    'create_vocabulary',
    'get_drug_info',
    'BiomedicalPreprocessor',
    'download_and_extract_zip',
]

__version__ = '2.0.0'