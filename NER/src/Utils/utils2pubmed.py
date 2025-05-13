"""
PubMed Data Retrieval Utility

This module provides functions to retrieve metadata from PubMed using both
MetaPub and Biopython libraries. It fetches article details such as PMIDs, 
titles, and abstracts using PMC IDs or PMIDs.

Functions:
    - get_pmid(pmcid): Convert PMC ID to PMID
    - get_title_by_metapub(pmcid): Get article title using PMC ID via MetaPub
    - get_title_by_bio(pmid): Get article title using PMID via Biopython
    - get_abstract_by_bio(pmid): Retrieve article abstract using PMID
"""

from metapub import PubMedFetcher
from Bio import Entrez

# Configure Entrez with your email for API access
Entrez.email = 'YOUR_EMAIL@example.com'  # IMPORTANT: Replace with your email

# ------------------------------------ PMID RETRIEVAL ------------------------------------

def get_pmid(pmcid):
    """
    Convert a PMC ID to its corresponding PubMed ID.
    
    Args:
        pmcid (str): The PMC ID of the article
        
    Returns:
        str: The corresponding PMID if found, empty list otherwise
    """
    try:
        article = PubMedFetcher().article_by_pmcid(pmcid)
        return article.pmid
    except Exception:
        return []

# ------------------------------------ TITLE RETRIEVAL -----------------------------------

def get_title_by_metapub(pmcid):
    """
    Retrieve an article's title using its PMC ID via MetaPub.
    
    Args:
        pmcid (str): The PMC ID of the article
        
    Returns:
        str: The article title if found, empty list otherwise
    """
    try:
        article = PubMedFetcher().article_by_pmcid(pmcid)
        return article.title
    except Exception:
        return []

def get_title_by_bio(pmid):
    """
    Retrieve an article's title using its PMID via Biopython.
    
    Args:
        pmid (str): The PMID of the article
        
    Returns:
        str: The article title if found, empty list otherwise
    """
    try:
        handle = Entrez.esummary(db="pubmed", id=pmid, retmode="xml")
        record = Entrez.parse(handle)
        return record['Title']
    except Exception:
        return []

# ---------------------------------- ABSTRACT RETRIEVAL ---------------------------------

def get_abstract_by_bio(pmid):
    """
    Retrieve an article's abstract using its PMID via Biopython.
    
    Args:
        pmid (str): The PMID of the article
        
    Returns:
        str: The article abstract if found, empty list otherwise
    """
    try:
        handle = Entrez.efetch(db="pubmed", id=pmid, retmode="xml")
        record = Entrez.read(handle)
        handle.close()
        
        article = record['PubmedArticle'][0]['MedlineCitation']
        abstract = ""
        
        # Some documents have no English abstract
        if 'Abstract' in article['Article'].keys():
            eng_content = article['Article']['Abstract']
            for element in eng_content['AbstractText']:
                abstract += element
                
        return abstract
    except Exception:
        return []