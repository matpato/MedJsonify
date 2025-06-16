###############################################################################
#                                                                             #  
# @file: extract_files.py                                                     #  
# @description: Extracts and copies specific files from source to destination #
# @date: May 2025                                                             #
# @version: 2.1                                                               #  
#                                                                             #  
# This script selectively extracts and copies specific files (XML, etc.)      #
# from their downloaded source directories to the appropriate destination     #
# directories based on the file source type (dailymed, purplebook, etc.).     #
# It handles different extraction patterns based on the source type.          #
#                                                                             #  
###############################################################################

import os
import shutil
import glob
from tqdm import tqdm
from upload.upload_loader import UploadLoader
import datetime

# OBJECTIVE: Initialize configuration and set up environment
# Load configuration for file paths and directories
config = UploadLoader()
downloads_dir = config.get_downloads_dir()
selected_directories = config.get_selected_directories()
dest_directories = config.get_dest_directories()
source_paths = config.get_source_paths()
file_patterns = config.get_file_patterns()

# -------------------------------------------------------------------------------------------
# UTILITY FUNCTIONS
# -------------------------------------------------------------------------------------------

def copy_files(src_directory, dest_directory, file_pattern):
    """
    Copy files matching the pattern from source directory to destination.
    
    Args:
        src_directory (str): Source directory to search for files
        dest_directory (str): Destination directory where files will be copied
        file_pattern (str): Pattern to match files (e.g., '*.xml', 'products.txt')
    """
    # OBJECTIVE: Create destination directory if it doesn't exist
    if not os.path.exists(dest_directory):
        try:
            os.makedirs(dest_directory)
        except PermissionError:
            print(f"Insufficient permissions to create directory: {dest_directory}")
            return

    if '*' in file_pattern:
        matching_files = []
        for root, _, files in os.walk(src_directory):
            for file in files:
                if glob.fnmatch.fnmatch(file, file_pattern):
                    matching_files.append(os.path.join(root, file))
    else:
        matching_files = [os.path.join(src_directory, file_pattern)]

    # OBJECTIVE: Copy all matching files to the destination with progress tracking
    for src_file in tqdm(matching_files, desc=f"Copying {file_pattern} files", unit="file"):
        if os.path.exists(src_file):
            shutil.copy(src_file, dest_directory)

def get_previous_month_csv_pattern():
    now = datetime.datetime.now()
    prev_month = now.replace(day=1) - datetime.timedelta(days=1)
    # Exemplo: purplebook-search-may-data-download.csv
    month_name = prev_month.strftime('%B').lower()  # 'may'
    return f"purplebook-search-{month_name}-data-download.csv"

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
    source_type = selected_directories[i]
    base_dir = os.path.splitext(file_filenames[i])[0]

    if source_type == "purplebook":
        src_file = os.path.join(downloads_dir, get_previous_month_csv_pattern())
        dest_directory = dest_directories[i]
        if not os.path.exists(dest_directory):
            os.makedirs(dest_directory)
        if os.path.exists(src_file):
            shutil.copy(src_file, dest_directory)
            print(f"Copied {src_file} to {dest_directory}")
        else:
            print(f"File not found: {src_file}")

    elif source_type == 'orangebook':
        src_file = os.path.join(downloads_dir, source_paths[i], file_patterns[i])
        dest_directory = dest_directories[i]
        if not os.path.exists(dest_directory):
            os.makedirs(dest_directory)
        if os.path.exists(src_file):
            shutil.copy(src_file, dest_directory)
            print(f"Copied {src_file} to {dest_directory}")
        else:
            print(f"File not found: {src_file}")

    else:
        if source_paths[i] == '.':
            src_directory = downloads_dir
        else:
            src_directory = os.path.join(downloads_dir, base_dir, source_paths[i])
        file_pattern = file_patterns[i]
        copy_files(src_directory, dest_directories[i], file_pattern)