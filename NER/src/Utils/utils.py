"""
File System Utility Module

This module provides general-purpose functions for file system operations,
entity handling, and parameter processing. It facilitates creating directories 
and files, managing blacklists, saving metadata, and handling command-line inputs.

Functions:
    - File System Operations:
        - new_folder(path): Create a new directory
        - new_file(file): Create a new file if it doesn't exist
        - set_blacklist(file, line): Add content to a blacklist file
        - save_metadata(file, line): Save process metadata to a file
        - create_entities_folder(src): Create and prepare entity directories
    
    - Parameter Processing:
        - input_parameters(args): Process command-line arguments for lexicon selection
"""

import os
from pathlib import Path

# ---------------------------- FILE SYSTEM OPERATIONS ----------------------------

def new_folder(path):
    """
    Create a new directory at the specified path if it doesn't exist.
    
    Args:
        path (str): Path where the directory should be created
    """
    try:
        if not os.path.exists(path):
            os.makedirs(path)
    except OSError as error:
        print(error)

def new_file(file):
    """
    Create a new empty file if it doesn't exist.
    
    Args:
        file (str): Path and name of the file to be created
    """
    try:
        if not os.path.isfile(file):
            f = open(file, 'w')
    except OSError as error:
        print(error)  

# ---------------------------- BLACKLIST MANAGEMENT -----------------------------

def set_blacklist(file, line):
    """
    Add a new entry to a blacklist file. The blacklist contains all invalid articles,
    such as non-authors, non-entities, etc.
    
    Args:
        file (str): Path to the blacklist file
        line (str): Content to add to the blacklist
    """
    new_file(file)
    with open(file, 'r+') as f:
        content = f.read()
        f.seek(0, 0)
        f.write(line.rstrip('\r\n') + '\n')
        f.write(content)
        f.close()

# ----------------------------- METADATA MANAGEMENT -----------------------------

def save_metadata(file, line):
    """
    Save metadata about the process to a text file, adding a separator
    between entries for readability.
    
    Args:
        file (str): Path to the metadata file
        line (str): Metadata content to save
    """
    new_file(file)    
    with open(file, 'r+') as f:
        content = f.read()
        f.seek(0, 0)
        f.write(line.rstrip('\r\n') + '\n')
        f.write('------------------------------------------------------' + '\n' + content)
        f.close()

# -------------------------- DIRECTORY STRUCTURE MANAGEMENT -------------------

def create_entities_folder(src):
    """
    Create a dedicated folder for entities based on the source directory name.
    This function navigates to the source directory, gets its name, returns
    to the parent directory, and creates a new directory with "_entities" suffix.
    
    Args:
        src (str): Path to the source directory
        
    Returns:
        tuple: (input_dir, output_dir) paths for input and entity directories
    """
    # Change the current working directory to the source path 
    os.chdir(src)
    
    # Get the base name of the current directory
    input_dir = os.path.basename(os.getcwd())
    
    # Return to the parent directory  
    os.chdir('..')
    
    # Create a new directory with "_entities" suffix if it doesn't exist
    entity_dir = input_dir.rstrip("/") + "_entities/"
    if not os.path.exists(entity_dir):
        os.makedirs(entity_dir)
    
    return input_dir, entity_dir
    
# -------------------------- PARAMETER PROCESSING ------------------------------

def input_parameters(args):
    """
    Process command-line arguments to determine which lexicons to use.
    If no lexicons are provided, return a default list.
    
    Args:
        args (list): Command-line arguments
        
    Returns:
        list: Names of lexicons to be processed
    """
    # If only program name and one argument are provided, use default lexicons
    if len(args) == 2:    
        return ["chebi", "do", "go", "hpo", "taxon", "cido"]
        
    # Otherwise, use lexicons provided by the user
    lexicons = []
    for i in args[2:]:
        lexicons.append(i)
    print(f'Entities to be found: {lexicons}')
    
    return lexicons