###############################################################################
#                                                                             #  
# @file: unzip_directories.py                                                 #  
# @description: Extracts ZIP files from downloads directory                   #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This script extracts ZIP files downloaded from various sources and performs #
# recursive extraction for nested ZIP files. It provides progress tracking    #
# during extraction and cleans up the original ZIP files afterward.           #
#                                                                             #  
###############################################################################

import zipfile
import os
from tqdm import tqdm
from upload.upload_loader import UploadLoader

# OBJECTIVE: Load configuration for processing downloaded files
# Initialize the configuration loader to get file paths and settings
config = UploadLoader()
downloads_dir = config.get_downloads_dir()

# -------------------------------------------------------------------------------------------
# UTILITY FUNCTIONS
# -------------------------------------------------------------------------------------------

def unzip_file(zip_path, extract_to):
    """
    Extract a ZIP file to the specified directory.
    
    Args:
        zip_path (str): Path to the ZIP file
        extract_to (str): Directory where files should be extracted
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

# -------------------------------------------------------------------------------------------

def unzip_all_in_directory(directory):
    """
    Recursively extract all ZIP files found in a directory and its subdirectories.
    
    Args:
        directory (str): Directory to search for ZIP files
    """
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.zip'):
                zip_path = os.path.join(root, file)
                # Create extraction directory with same name as ZIP file (without extension)
                extract_to = os.path.splitext(zip_path)[0]
                unzip_file(zip_path, extract_to)
                # Recursively process extracted directories for nested ZIPs
                unzip_all_in_directory(extract_to)

# -------------------------------------------------------------------------------------------

def unzip_file_with_progress(zip_path, extract_to):
    """
    Extract a ZIP file with progress tracking using tqdm.
    
    Args:
        zip_path (str): Path to the ZIP file
        extract_to (str): Directory where files should be extracted
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        for file in tqdm(file_list, desc="Decompressing", unit="file"):
            zip_ref.extract(file, extract_to)

# -------------------------------------------------------------------------------------------
# MAIN EXECUTION
# -------------------------------------------------------------------------------------------

# OBJECTIVE: Read the list of ZIP files to process
# The filename.txt contains the list of ZIP files downloaded
with open(os.path.join(downloads_dir, 'filename.txt'), 'r') as f:
    zip_filenames = f.readlines()
    for i in range(len(zip_filenames)):
        zip_filenames[i] = zip_filenames[i].strip('\n')

# OBJECTIVE: Process each ZIP file in the list
# Generate full paths for each ZIP file
zip_file_paths = [os.path.join(downloads_dir, zip_filename) for zip_filename in zip_filenames]

# OBJECTIVE: Extract all ZIP files with progress tracking and handle nested ZIPs
for zip_file_path in zip_file_paths:
    if zip_file_path.endswith('.zip'):
        # Verify if the file is a valid ZIP
        if zipfile.is_zipfile(zip_file_path):
            # Create extraction directory with same name as ZIP file (without extension)
            extract_to = os.path.splitext(zip_file_path)[0]
            # Extract with progress tracking
            unzip_file_with_progress(zip_file_path, extract_to)
            # Recursively extract any nested ZIP files
            unzip_all_in_directory(extract_to)
            
            # OBJECTIVE: Clean up by removing the original ZIP file after extraction
            os.remove(zip_file_path)
        else:
            print(f"The file {zip_file_path} is not a valid ZIP file.")
    else:
        print(f"The file {zip_file_path} is not a .zip file.")