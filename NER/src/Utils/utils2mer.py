"""
MER Ontology Management Utility

This module provides functions to update and manage MER (Minimal Entity Recognition)
ontologies. It handles downloading, processing, and cleaning of various ontologies
including DOID, GO, HPO, ChEBI, TAXON, CIDO, and ORDO.

Functions:
    - update_mer(lexicon): Update specified MER ontologies
    - items_in_blacklist(doc, lexicon): Filter document content against blacklists
"""

import sys
import os
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Add MER package to path
repo_path = os.path.abspath("/opt/airflow/dags/NER/merpy/merpy")
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)
import merpy

# Download required NLTK resources
nltk.download('punkt')
nltk.download('stopwords')

# -------------------------------- ONTOLOGY MANAGEMENT ---------------------------------

def update_mer(lexicon):
    """
    Update specified MER ontologies by downloading the latest OBO/OWL files,
    processing them, and cleaning obsolete or unwanted entries.
    
    Args:
        lexicon (list): List of ontology identifiers to update. If empty,
                       all supported ontologies will be updated.
    """
    print("Download latest obo files and process lexicons")
    
    # If lexicon list is empty, update all supported ontologies
    if len(lexicon) == 0:
        lexicon = ["doid", "go", "hpo", "chebi", "taxon", "cido"]
    
    # Process each requested ontology
    for l in lexicon:
        # Disease Ontology
        if l == 'doid':
            merpy.download_lexicon("http://purl.obolibrary.org/obo/doid.owl", "do", ltype="owl")
            merpy.process_lexicon("do", ltype="owl")
            merpy.delete_obsolete("do")
        
        # Gene Ontology
        if l == 'go':    
            merpy.download_lexicon("http://purl.obolibrary.org/obo/go.owl", "go", ltype="owl")
            merpy.process_lexicon("go", ltype="owl")
            merpy.delete_obsolete("go")
        
        # Human Phenotype Ontology
        if l == 'hp':    
            merpy.download_lexicon("http://purl.obolibrary.org/obo/hp.owl", "hpo", ltype="owl")
            merpy.process_lexicon("hpo", ltype="owl")
            merpy.delete_obsolete("hpo")
            # Remove problematic entities
            merpy.delete_entity("protein", "hpo")
            merpy.delete_entity_by_uri("http://purl.obolibrary.org/obo/PATO_0000070", "hpo")
        
        # Chemical Entities of Biological Interest
        if l == 'chebi':
            merpy.download_lexicon(
                "http://purl.obolibrary.org/obo/chebi/chebi_lite.owl",
                "chebi",
                ltype="owl",
            )
            merpy.process_lexicon("chebi", ltype="owl")
            merpy.delete_obsolete("chebi")
            # Remove problematic entities
            merpy.delete_entity("protein", "chebi")
            merpy.delete_entity("polypeptide chain", "chebi")
            merpy.delete_entity("one", "chebi")
        
        # NCBI Taxonomy
        if l == 'taxon':
            merpy.download_lexicon("http://purl.obolibrary.org/obo/ncbitaxon.owl", "taxon", ltype="owl")
            merpy.process_lexicon("taxon", ltype="owl")
            merpy.delete_obsolete("taxon")
            merpy.delete_entity("data", "taxon")
        
        # Coronavirus Infectious Disease Ontology
        if l == 'cido':
            merpy.download_lexicon(
                "https://raw.githubusercontent.com/CIDO-ontology/cido/master/src/ontology/cido.owl",
                "cido",
                "owl",
            )
            merpy.process_lexicon("cido", "owl")
            merpy.delete_obsolete("cido")
            merpy.delete_entity("protein", "cido")

# ------------------------------ TEXT FILTERING UTILITIES -------------------------------

def items_in_blacklist(doc, lexicon):
    """
    Filter document text against blacklists to remove words that may distort
    ontology classifications. Combines standard English stopwords with
    ontology-specific blacklisted terms.
    
    Note: This function appears to be unused in the current codebase.
    
    Args:
        doc (str): Document text to filter
        lexicon (str): Ontology identifier to select the appropriate blacklist
        
    Returns:
        str: Filtered document text with blacklisted words removed
    """
    # Initialize blacklist
    black_list = []
    
    # Get English stopwords
    all_stopwords = stopwords.words('english')
    
    # Select appropriate blacklist file based on ontology
    filename = ''
    if lexicon == 'chebi':
        filename = 'chebi.txt'
    elif lexicon == 'doid':
        filename = 'doid.txt'
    elif lexicon == 'go':
        filename = 'go.txt'        
    elif lexicon == 'hp':
        filename = 'hp.txt'
    elif lexicon == 'ordo':
        filename = 'ordo.txt'
    
    # Load blacklist if file exists
    blacklist_path = os.path.join('/opt/airflow/dags/NER/data/blacklists/', filename)
    if os.path.isfile(blacklist_path):
        with open(blacklist_path, 'r') as file:
            black_list = [content.rstrip() for content in file.readlines()]
        all_stopwords.extend(black_list)
    
    # Tokenize document and remove stopwords
    doc_tokens = word_tokenize(doc)
    doc_tokens_sw = [word for word in doc_tokens if word not in all_stopwords]
    
    # Join tokens back into text
    return ' '.join(doc_tokens_sw)