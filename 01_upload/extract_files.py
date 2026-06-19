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
import fnmatch
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
    Only searches the specified directory (non-recursive) to respect source_paths configuration.
    
    Args:
        src_directory (str): Source directory to search for files (e.g., .../prescription)
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

    # Check if source directory exists
    if not os.path.exists(src_directory):
        print(f"Source directory does not exist: {src_directory}")
        return

    if '*' in file_pattern:
        # Use glob to find matching files only in the specified directory (non-recursive)
        pattern_path = os.path.join(src_directory, file_pattern)
        matching_files = glob.glob(pattern_path)
        
        # If no files found, also check subdirectories ONE level deep
        # This handles cases where files might be in immediate subdirectories
        if not matching_files:
            pattern_path_recursive = os.path.join(src_directory, '*', file_pattern)
            matching_files = glob.glob(pattern_path_recursive)
    else:
        # Specific file pattern (e.g., 'products.txt')
        matching_files = [os.path.join(src_directory, file_pattern)]

    if not matching_files:
        print(f"No files matching pattern '{file_pattern}' found in {src_directory}")
        return

    print(f"Found {len(matching_files)} file(s) matching '{file_pattern}' in {src_directory}")

    # OBJECTIVE: Copy all matching files to the destination with progress tracking
    for src_file in tqdm(matching_files, desc=f"Copying {file_pattern} files", unit="file"):
        if os.path.exists(src_file) and os.path.isfile(src_file):
            try:
                shutil.copy(src_file, dest_directory)
            except Exception as e:
                print(f"Error copying {src_file}: {e}")

def get_previous_month_csv_pattern():
    now = datetime.datetime.now()
    prev_month = now.replace(day=1) - datetime.timedelta(days=1)
    month_name = prev_month.strftime('%B').lower() 
    return f"purplebook-search-{month_name}-data-download.csv"

# -------------------------------------------------------------------------------------------
# MAIN EXECUTION
# -------------------------------------------------------------------------------------------

# OBJECTIVE: Read the list of files to process from filename.txt
with open(os.path.join(downloads_dir, 'filename.txt'), 'r') as f:
    file_filenames = [line.strip() for line in f.readlines()]

print(f"Processing {len(file_filenames)} file(s) from filename.txt")

# OBJECTIVE: Process each file according to its source type
for i, filename in enumerate(file_filenames):
    # Determine source type based on filename pattern
    if 'purplebook' in filename.lower():
        source_type = 'purplebook'
        idx = selected_directories.index('purplebook')
    elif 'orangebook' in filename.lower():
        source_type = 'orangebook'
        idx = selected_directories.index('orangebook')
    elif 'dm_spl' in filename.lower() or 'dailymed' in filename.lower():
        source_type = 'dailymed'
        idx = selected_directories.index('dailymed')
    else:
        print(f"Unknown file type: {filename}, skipping...")
        continue

    print(f"\n[{i+1}/{len(file_filenames)}] Processing {source_type}: {filename}")
    
    base_dir = os.path.splitext(filename)[0]

    if source_type == "purplebook":
        src_file = os.path.join(downloads_dir, get_previous_month_csv_pattern())
        dest_directory = dest_directories[idx]
        if not os.path.exists(dest_directory):
            os.makedirs(dest_directory)
        if os.path.exists(src_file):
            shutil.copy(src_file, dest_directory)
            print(f"  ✓ Copied {src_file} to {dest_directory}")
        else:
            print(f"  ✗ File not found: {src_file}")

    elif source_type == 'orangebook':
        # For orangebook, the extracted directory structure is: orangebook/orangebook/products.txt
        src_directory = os.path.join(downloads_dir, base_dir, source_paths[idx])
        src_file = os.path.join(src_directory, file_patterns[idx])
        dest_directory = dest_directories[idx]
        
        if not os.path.exists(dest_directory):
            os.makedirs(dest_directory)
        if os.path.exists(src_file):
            shutil.copy(src_file, dest_directory)
            print(f"  ✓ Copied {src_file} to {dest_directory}")
        else:
            print(f"  ✗ File not found: {src_file}")

    elif source_type == 'dailymed':
        # For dailymed, we need to go to the prescription subdirectory
        # Structure: dm_spl_monthly_update_dec2025/prescription/*.xml
        if source_paths[idx] == '.':
            src_directory = os.path.join(downloads_dir, base_dir)
        else:
            src_directory = os.path.join(downloads_dir, base_dir, source_paths[idx])
        
        print(f"  Source directory: {src_directory}")
        print(f"  File pattern: {file_patterns[idx]}")
        print(f"  Destination: {dest_directories[idx]}")
        
        if not os.path.exists(src_directory):
            print(f"  ✗ Source directory does not exist: {src_directory}")
            continue
        
        # Copy files using the configured pattern (*.xml from prescription folder only)
        copy_files(src_directory, dest_directories[idx], file_patterns[idx])

print("\n✓ File extraction complete")