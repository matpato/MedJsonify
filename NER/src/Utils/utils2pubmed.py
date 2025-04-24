###############################################################################
#                                                                             #  
# @author: Matilde Pato (Adapted from André Lamurias)                         #  
# @email: matilde.pato@gmail.com                                              #
# @date: 31 Mar 2021                                                          #
# @version: 1.0                                                               #  
# Lasige - FCUL                                                               #
#                                                                             #  
# @last update:                                                               #  
#   version 1.1: 01 Oct 2021 - Update some functions  (after line 114)        #      
#   (author: matilde.pato@gmail.com  )                                        # 
###############################################################################
#
# This file get abstracts, authors, year based on PubMed
#

### -- PMID
from metapub import PubMedFetcher
from Bio import Entrez
Entrez.email = 'matilde.pato@gmail.com'

# --------------------------------------------------------------------------- #

def get_pmid(pmcid):
    '''
    Return PubMed ID
    
    :param  pmcid:
    :return pmid:         
    '''
    try:
        article = PubMedFetcher().article_by_pmcid(pmcid)
        return article.pmid
    except:
        return []    


# --------------------------------------------------------------------------- #

def get_title_by_metapub(pmcid):
    '''
    Return PubMed ID
    
    :param  pmcid:
    :return pmid:         
    '''
    try:
        #article = fetch.article_by_pmid(pmid)
        article = PubMedFetcher().article_by_pmcid(pmcid)
        return article.title
    except:
        return []     

# --------------------------------------------------------------------------- #

def get_title_by_bio(pmid):
    ''' 
    Get PubMed year using Bio

    :param  pmid: PMID' article
    :return year
    '''
    try:
        handle = Entrez.esummary(db="pubmed", id=pmid, retmode="xml")
        record = Entrez.parse(handle)
        return record['Title']
    except:
        return [] 

# --------------------------------------------------------------------------- #

def get_abstract_by_bio(pmid):
    ''' 
    Get PubMed year using Bio

    :param  pmid: PMID' article
    :return year
    '''
    try:
        handle = Entrez.efetch(db="pubmed", id=pmid, retmode="xml")
        record = Entrez.read(handle)
        handle.close()
        article = record['PubmedArticle'][0]['MedlineCitation']
        abstract = str()
                
        if 'Abstract' in article['Article'].keys(): # Some documents have no english abstract
            eng_content = article['Article']['Abstract']
        for element in eng_content['AbstractText']:
            abstract += element
        return abstract
    except:
        return [] 