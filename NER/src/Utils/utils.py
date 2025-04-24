###############################################################################
#                                                                             #  
# @author: Matilde Pato                                                       #  
# @email: matilde.pato@gmail.com                                              #
# @date: 29 Apr 2021                                                          #
# @version: 1.0                                                               #  
# Lasige - FCUL                                                               #
#                                                                             #  
# @last update:                                                               #  
#   version 1.1: 01 Oct 2021 - News functions were used (after line 100)      #      
#   (author: matilde.pato@gmail.com  )                                        # 
#                                                                             #   
#                                                                             #  
###############################################################################

import os
from pathlib import Path
from urllib.parse import quote

# --------------------------------------------------------------------------- #

def new_folder(path):

    try:
        if not os.path.exists(path):
            os.makedirs(path)
    except OSError as error:
        print(error)
        
# --------------------------------------------------------------------------- #

def new_file(file):

    try:
        if not os.path.isfile(file):
            f = open(file, 'w')
    except OSError as error:
        print(error)  

# --------------------------------------------------------------------------- #

def set_blacklist(file, line):
    '''
    This function receives the article to and saves them in the
    blacklist file. The backlist contains all invalid articles, such
    as non-authors, non-entities, and others
    :param  filename: name of txt file
            line: all content
    :return none        
    '''
    
    new_file(file)
    with open(file, 'r+') as f:
        content = f.read()
        f.seek(0, 0)
        f.write(line.rstrip('\r\n') + '\n')
        f.write(content)
        f.close()

# --------------------------------------------------------------------------- #

def save_metadata(file, line):
    '''
    This function will save all metadata about the process in txt file
    :param  filename: name of txt file
            line: all content
    :return none        
    '''

    new_file(file)    
    with open(file, 'r+') as f:
        content = f.read()
        f.seek(0, 0)
        f.write(line.rstrip('\r\n') + '\n')
        f.write('------------------------------------------------------' + '\n' + content)
        f.close()

# ---------------------------------------------------------------------------------------- #

def create_entities_folder(src):

    # Change the current working directory to path 
    os.chdir(src)
    # input_dir is new
    input_dir = os.path.basename(os.getcwd())
    # Return one folder back  
    os.chdir('..')
    
    # Create a new directory if not exists
    if not os.path.exists(input_dir.rstrip("/") + "_entities/"):
        os.makedirs(input_dir.rstrip("/") + "_entities/")
    
    output_dir = input_dir.rstrip("/") + "_entities/"
    return input_dir, output_dir
    
# ---------------------------------------------------------------------------------------- #

def input_parameters(args):

    if len(args) == 2:    
        return ["chebi", "do", "go", "hpo", "taxon", "cido"]
    # if entities is defined by user then saved it in a list
    lexicons = []
    for i in args[2:]:
        lexicons.append(i)
    print(f'Entities to be found: {lexicons}')    
    # else all entities are listed    
    
    return lexicons    
