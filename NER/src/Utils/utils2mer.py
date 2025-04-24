
###############################################################################
#                                                                             #  
# @author: Matilde Pato (Adapted from André Lamurias)                         #  
# @email: matilde.pato@gmail.com                                              #
# @date: 24 april 2025                                                          #
# @version: 1.1                                                               #  
# Lasige - FCUL                                                               #
#                                                                             #  
# @last update:                                                               #  
#   version 1.1:                                                              #      
#   (author: )                                                                #  
###############################################################################
#
# Import stop words vocabulary and tokenizer. Stop words are common words of a 
# given language (for example the words 'the', 'and', 'in'). A typical pre-p
# rocessing step is to tokenize the text and remove the stopwords. For that, 
# we are going to import NLTK's list of english stopwords and use the NLTK 
# tokenizer.
# Update MER ontologies, including ORDO (Orphanet Rare Disease Ontology)

import sys
import os

repo_path = os.path.abspath("/opt/airflow/dags/NER/merpy/merpy")
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)
import merpy

## --- tokens
import nltk 
nltk.download('punkt')
from nltk.corpus import stopwords
nltk.download('stopwords')
from nltk.tokenize import word_tokenize


# --------------------------------------------------------------------------- #

def update_mer(lexicon):
    '''
    Update MER ontologies
    '''
    print("Download latest obo files and process lexicons")
    #merpy.download_mer()
    if len(lexicon) == 0:
        lexicon = ["doid", "go", "hpo", "chebi", "taxon", "cido","ordo"] 
    for l in lexicon:
        if l == 'doid':
            merpy.download_lexicon("http://purl.obolibrary.org/obo/doid.owl", "do", ltype="owl")
            
            merpy.process_lexicon("do", ltype="owl")
            merpy.delete_obsolete("do")

        if l == 'go':    
            merpy.download_lexicon("http://purl.obolibrary.org/obo/go.owl", "go", ltype="owl")
            merpy.process_lexicon("go", ltype="owl")
            merpy.delete_obsolete("go")
        if l == 'hp':    
            merpy.download_lexicon("http://purl.obolibrary.org/obo/hp.owl", "hpo", ltype="owl")
            merpy.process_lexicon("hpo", ltype="owl")
            merpy.delete_obsolete("hpo")
            merpy.delete_entity("protein", "hpo")
            merpy.delete_entity_by_uri("http://purl.obolibrary.org/obo/PATO_0000070", "hpo")
        if l == 'chebi':
            merpy.download_lexicon("http://purl.obolibrary.org/obo/chebi/chebi_lite.owl",#"ftp://ftp.ebi.ac.uk/pub/databases/chebi/ontology/chebi.owl",
                "chebi",
                ltype="owl",
            )
            merpy.process_lexicon("chebi", ltype="owl")
            merpy.delete_obsolete("chebi")
            merpy.delete_entity("protein", "chebi")
            merpy.delete_entity("polypeptide chain", "chebi")
            merpy.delete_entity("one", "chebi")
        if l == 'taxon':
            merpy.download_lexicon("http://purl.obolibrary.org/obo/ncbitaxon.owl", "taxon", ltype="owl")
            merpy.process_lexicon("taxon", ltype="owl")
            merpy.delete_obsolete("taxon")
            merpy.delete_entity("data", "taxon")
        if l == 'cido':
            merpy.download_lexicon("https://raw.githubusercontent.com/CIDO-ontology/cido/master/src/ontology/cido.owl",
                "cido",
                "owl",
            )
            merpy.process_lexicon("cido", "owl")
            merpy.delete_obsolete("cido")
            merpy.delete_entity("protein", "cido")
        if l == 'ordo':
            merpy.download_lexicon("https://data.bioontology.org/ontologies/ORDO/submissions/30/download?apikey=8b5b7825-538d-40e0-9e9e-5ab9274a9aeb", "ordo", ltype="owl")
            merpy.process_lexicon("ordo", ltype="owl")
            merpy.delete_obsolete("ordo")    

# --------------------------------------------------------------------------- #

def items_in_blacklist(doc, lexicon):
    '''
    Clear words from document that may distort the 
    classification of the ontologies
    :param  doc: document
            lexicon: prefix of the ontology
    :return doc       
    '''
    black_list = []
    
    # Removing stop words with NLTK  and aditional text
    all_stopwords = stopwords.words('english')
    filename =''
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
   
    if os.path.isfile(os.path.join('/opt/airflow/dags/NER/data/blacklists/',filename)):  
        with open(os.path.join('/opt/airflow/dags/NER/data/blacklists/',filename), 'r') as file:
            black_list = [content.rstrip() for content in file.readlines()]
        all_stopwords.extend(black_list) 

    # Tokenize and remove stop words 
    doc_tokens = word_tokenize(doc)
    doc_tokens_sw = [word for word in doc_tokens if not word in all_stopwords]
    
    return (' ').join(doc_tokens_sw)