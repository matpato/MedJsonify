###############################################################################
#                                                                             #  
# @file: extract_files.py                                                     #  
# @description: Extracts and copies specific files from source to destination #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This script selectively extracts and copies specific files (XML, etc.)      #
# from their downloaded source directories to the appropriate destination     #
# directories based on the file source type (dailymed, purplebook, etc.).     #
# It handles different extraction patterns based on the source type.          #
#                                                                             #  
###############################################################################

import os
import shutil
from tqdm import tqdm
from upload.upload_loader import UploadLoader

# OBJECTIVE: Initialize configuration and set up environment
# Load configuration for file paths and directories
config = UploadLoader()
downloads_dir = config.get_downloads_dir()
selected_directories = config.get_selected_directories()
dest_directories = config.get_dest_directories()

# -------------------------------------------------------------------------------------------
# UTILITY FUNCTIONS
# -------------------------------------------------------------------------------------------

def copy_xml_files(src_directory, dest_directory):
    """
    Copy all XML files from source directory (including subdirectories) to the destination.
    
    Args:
        src_directory (str): Source directory to search for XML files
        dest_directory (str): Destination directory where files will be copied
    """
    # OBJECTIVE: Create destination directory if it doesn't exist
    if not os.path.exists(dest_directory):
        try:
            os.makedirs(dest_directory)
        except PermissionError:
            print(f"Insufficient permissions to create directory: {dest_directory}")
            return
    
    # OBJECTIVE: Find all XML files in the source directory and subdirectories
    xml_files = []
    for root, _, files in os.walk(src_directory):
        for file in files:
            if file.endswith('.xml'):
                xml_files.append(os.path.join(root, file))
    
    # OBJECTIVE: Copy all XML files to the destination with progress tracking
    for src_file in tqdm(xml_files, desc="Copying XML files", unit="file"):
        shutil.copy(src_file, dest_directory)

# -------------------------------------------------------------------------------------------
# MAIN EXECUTION
# -------------------------------------------------------------------------------------------

# OBJECTIVE: Read the list of files to process from filename.txt
with open(os.path.join(downloads_dir, 'filename.txt'), 'r') as f:
    file_filenames = f.readlines()
    for i in range(len(file_filenames)):
        file_filenames[i] = file_filenames[i].strip('\n')

# OBJECTIVE: Process each file according to its source type
for i in range(len(file_filenames)):
    # CASE 1: Process DailyMed files (extract all XML files from prescription directory)
    if selected_directories[i] == 'dailymed':
        # Source directory is in downloads_dir/extracted_folder/prescription
        src_directory = os.path.expanduser(f'{downloads_dir}/{os.path.splitext(file_filenames[i])[0]}/prescription')
        # Copy all XML files from source to destination
        copy_xml_files(src_directory, dest_directories[i])
    
    # CASE 2: Process PurpleBook files (copy the entire file directly)
    elif selected_directories[i] == 'purplebook':
        # Source file is in downloads_dir
        src_file = os.path.join(downloads_dir, file_filenames[i])
        # Copy file directly to destination
        shutil.copy(src_file, dest_directories[i])
    
    # CASE 3: Process OrangeBook files (copy only the products.txt file)
    elif selected_directories[i] == 'orangebook':
        # Source file is products.txt in orangebook subdirectory
        src_file = os.path.join(downloads_dir, 'orangebook', 'products.txt')
        dest_directory = dest_directories[i]
        
        # Create destination directory if it doesn't exist
        if not os.path.exists(dest_directory):
            os.makedirs(dest_directory)
        
        # Copy products.txt file to destination
        shutil.copy(src_file, dest_directory)
        print(f"Copied {src_file} to {dest_directory}")