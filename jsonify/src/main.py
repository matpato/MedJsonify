###############################################################################
#                                                                             #  
# @file: main.py                                                              #  
# @description: Main entry point for the file conversion system               #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This module orchestrates the conversion of various file types (XML, CSV,    #
# TXT) to JSON format. It handles the entire process including file loading,  #
# conversion, duplicate removal, and detailed logging and reporting.          #
#                                                                             #  
###############################################################################

import os
import json
import xml.etree.ElementTree as ET
from glob import glob
from converter.python_converter import parse_xml_to_json, check_null_fields
from converter.xslt_converter import apply_xslt_to_xml
from converter.csv_converter import convert_file_to_json
from config_loader import ConfigLoader
import datetime

# -----------------------------------------------------------------------------------
# UTILITY FUNCTIONS
# -----------------------------------------------------------------------------------

def normalize_medication_name(name):
    """
    Normalize a medication name for consistent comparison.
    
    Args:
        name: The medication name to normalize
        
    Returns:
        str or None: Normalized name (lowercase, stripped) or None if input is None
    """
    if name:
        return name.lower().strip()
    return None

def load_processed_medications(file_path):
    """
    Load the set of previously processed medications from a file.
    
    Args:
        file_path (str): Path to the file containing processed medication names
        
    Returns:
        set: Set of normalized medication names
    """
    # OBJECTIVE: Build a set of previously processed medications to avoid duplicates
    processed = set()
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                med_name = normalize_medication_name(line)
                if med_name:
                    processed.add(med_name)
    return processed

def extract_medication_name_from_csv(file_path):
    """
    Extract the medication name from a CSV-derived JSON file.
    
    Args:
        file_path (str): Path to the JSON file
        
    Returns:
        str or None: Normalized medication name or None if not found
    """
    # OBJECTIVE: Extract medication name from CSV-converted JSON file
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return normalize_medication_name(data.get('Proper Name'))
    return None

def extract_medication_name_from_xml(file_path):
    """
    Extract the medication name from an XML-derived JSON file.
    
    Args:
        file_path (str): Path to the JSON file
        
    Returns:
        str or None: Normalized medication name or None if not found
    """
    # OBJECTIVE: Extract medication name from XML-converted JSON file
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return normalize_medication_name(data.get('name'))
    return None

# -----------------------------------------------------------------------------------
# LOGGING FUNCTIONS
# -----------------------------------------------------------------------------------

def write_log_summary(log_file_path, summary):
    """
    Write a detailed processing summary to the log file.
    
    Args:
        log_file_path (str): Path to the summary log file
        summary (dict): Summary data to write
    """
    # OBJECTIVE: Create a structured, timestamped summary log
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file_path, 'a', encoding='utf-8') as f:
        f.write(f"\n---------------------- Processing Summary [{timestamp}] ----------------------\n")
        # Iterate through the summary dictionary, handling nested dictionaries
        for key, value in summary.items():
            if isinstance(value, dict):
                f.write(f"{key}:\n")
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, dict):
                        f.write(f"  {sub_key}:\n")
                        for detail_key, detail_value in sub_value.items():
                            f.write(f"    {detail_key}: {detail_value}\n")
                    else:
                        f.write(f"  {sub_key}: {sub_value}\n")
            else:
                f.write(f"{key}: {value}\n")
        f.write(f"\n------------------------------------------------------------------------------\n")

def append_to_log(log_file_path, message):
    """
    Append a timestamped message to a log file.
    
    Args:
        log_file_path (str): Path to the log file
        message (str): Message to log
    """
    # OBJECTIVE: Add a timestamped entry to the specified log file
    with open(log_file_path, 'a', encoding='utf-8') as f:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {message}\n")

# -----------------------------------------------------------------------------------
# CORE PROCESSING FUNCTIONS
# -----------------------------------------------------------------------------------

def process_file_types(config_loader):
    """
    Process all configured file types, converting them to JSON format.
    
    This function handles the conversion of all file types, tracking statistics,
    removing duplicates, and generating detailed logs.
    
    Args:
        config_loader (ConfigLoader): The configuration loader object
        
    Returns:
        dict: A summary of the processing results
    """
    # OBJECTIVE: Load configuration parameters
    log_file = config_loader.get_log_file_path()  # missing_fields_log.txt
    unconverted_file = config_loader.get_unconverted_file_path()  # unconverted_files.txt
    processed_medications_file = config_loader.get_processed_medications_file_path()  # drugs.txt
    processing_summary_file = config_loader.get_summary_file_path()  # summary.txt
    conversion_method = config_loader.get_conversion_method()
    file_types = config_loader.get_file_types()
    
    # OBJECTIVE: Ensure log directories exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    os.makedirs(os.path.dirname(unconverted_file), exist_ok=True)
    os.makedirs(os.path.dirname(processed_medications_file), exist_ok=True)

    # OBJECTIVE: Initialize tracking variables for logging and statistics
    missing_fields_log = []
    converted_count = 0  
    unconverted_count = 0
    unconverted_files = []
    
    # Initialize counters for each file type
    file_counters = {file_type: {
        'initial': 0,             # Initial number of files found
        'converted': 0,           # Successfully converted files
        'unconverted': 0,         # Failed conversion files
        'skipped': 0,             # Files skipped during processing
        'removed_duplicates': 0,  # Duplicate files removed
        'files_before_cleaning': 0,  # Files before duplicate removal
        'files_after_cleaning': 0    # Files after duplicate removal
    } for file_type in file_types}
    
    # Initialize totals for summary statistics
    total_counters = {'initial': 0, 'converted': 0, 'unconverted': 0, 'skipped': 0, 'removed_duplicates': 0,
                      'files_before_cleaning': 0, 'files_after_cleaning': 0}

    # OBJECTIVE: Process each file type (XML, CSV, TXT)
    for file_type in file_types:
        # Get input and output directories for this file type
        input_folder = config_loader.get_input_folder_for_type(file_type)
        output_folder = config_loader.get_output_folder_for_type(file_type)
        
        # Ensure output directory exists
        if not os.path.exists(output_folder):
            os.makedirs(output_folder, exist_ok=True)
        
        # Find all files of the current type in the input folder
        input_files = glob(os.path.join(input_folder, f'*.{file_type}'))
        file_counters[file_type]['initial'] = len(input_files)
        total_counters['initial'] += len(input_files)
        
        # Log the number of files found
        process_msg = f"Processing {file_type} files: Found {len(input_files)} files in {input_folder}"
        print(process_msg)
        append_to_log(log_file, process_msg)

        # OBJECTIVE: Convert each input file to JSON format
        for input_file in input_files:
            output_file = os.path.join(output_folder, os.path.basename(input_file).replace(f'.{file_type}', '.json'))
            try:
                # CASE 1: Process XML files using the configured method (XSLT or Python)
                if file_type == 'xml':
                    if conversion_method == 'xslt':
                        xslt_path = os.path.join(os.path.dirname(__file__), '..', 'conversion_xslt.xslt')
                        json_data = apply_xslt_to_xml(xslt_path, input_file)
                    elif conversion_method == 'python':
                        json_data = parse_xml_to_json(input_file)
                    
                    # Check for missing fields in the converted data
                    missing_fields = check_null_fields(json_data)
                    if missing_fields:
                        missing_fields_log.append(f"File: {input_file}, Missing fields: {', '.join(missing_fields)}")
                    
                    # Write the converted data to the output file
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=4, ensure_ascii=False)
                    file_counters[file_type]['converted'] += 1
                    converted_count += 1

                # CASE 2: Process CSV files
                elif file_type == 'csv':
                    result = convert_file_to_json(input_file, output_folder, delimiter=",", skiprows=3)
                    if result:
                        file_counters[file_type]['converted'] += 1
                        converted_count += 1
                    else:
                        file_counters[file_type]['unconverted'] += 1
                        unconverted_count += 1
                        unconverted_files.append(input_file)

                # CASE 3: Process TXT files (with ~ delimiter)
                elif file_type == 'txt':
                    result = convert_file_to_json(input_file, output_folder, delimiter="~")
                    if result:
                        file_counters[file_type]['converted'] += 1
                        converted_count += 1
                    else:
                        file_counters[file_type]['unconverted'] += 1
                        unconverted_count += 1
                        unconverted_files.append(input_file)
            except Exception as e:
                # Track conversion failures
                file_counters[file_type]['unconverted'] += 1
                unconverted_count += 1
                unconverted_files.append(input_file)
                with open(unconverted_file, 'a', encoding='utf-8') as f:
                    f.write(f"{input_file} - Error: {str(e)}\n")
        
        # Update total counters for this file type
        total_counters['converted'] += file_counters[file_type]['converted']
        total_counters['unconverted'] += file_counters[file_type]['unconverted']

        # OBJECTIVE: Remove duplicate files based on medication name
        # Count files before cleaning
        files_before_cleaning = len(glob(os.path.join(output_folder, '*.json')))
        file_counters[file_type]['files_before_cleaning'] = files_before_cleaning
        total_counters['files_before_cleaning'] += files_before_cleaning
        
        before_cleaning_msg = f"[{file_type}] Files before cleaning duplicates: {files_before_cleaning}"
        print(before_cleaning_msg)
        append_to_log(log_file, before_cleaning_msg)
        
        # Clean duplicates and update counters
        removed_count = clean_repeated_medications(processed_medications_file, output_folder, file_type, log_file)
        file_counters[file_type]['removed_duplicates'] = removed_count
        total_counters['removed_duplicates'] += removed_count
        
        # Count files after cleaning
        files_after_clean = len(glob(os.path.join(output_folder, '*.json')))
        file_counters[file_type]['files_after_cleaning'] = files_after_clean
        total_counters['files_after_cleaning'] += files_after_clean
        
        # Log summary for this file type
        summary_msg = f"[{file_type}] Initial: {file_counters[file_type]['initial']}, Converted: {file_counters[file_type]['converted']}, " \
                      f"Unconverted: {file_counters[file_type]['unconverted']}, Removed duplicates: {removed_count}, " \
                      f"Final count: {files_after_clean}"
        print(summary_msg)
        append_to_log(log_file, summary_msg)

    # OBJECTIVE: Write final logs
    # Write list of unconverted files
    with open(unconverted_file, 'w', encoding='utf-8') as f:
        for file in unconverted_files:
            f.write(f"{file}\n")
    
    # Write missing fields log
    with open(log_file, 'w', encoding='utf-8') as f:
        for log_entry in missing_fields_log:
            f.write(f"{log_entry}\n")

    # OBJECTIVE: Create and write final processing summary
    summary = {
        "Total initial files": total_counters['initial'],
        "Total converted files": total_counters['converted'],
        "Total unconverted files": total_counters['unconverted'],
        "Total files before cleaning": total_counters['files_before_cleaning'],
        "Total files after cleaning": total_counters['files_after_cleaning'],
        "Total duplicates removed": total_counters['removed_duplicates'],
        "Breakdown by file type": file_counters
    }
    
    write_log_summary(processing_summary_file, summary)
    return summary

def clean_repeated_medications(processed_meds_file, output_folder, file_type, log_file):
    """
    Remove duplicate medication files based on medication name.
    
    Args:
        processed_meds_file (str): Path to the file tracking processed medications
        output_folder (str): Directory containing JSON files to check for duplicates
        file_type (str): The file type being processed ('xml', 'csv', etc.)
        log_file (str): Path to the log file for logging actions
        
    Returns:
        int: Number of duplicate files removed
    """
    # OBJECTIVE: Load previously processed medications
    processed_medications = load_processed_medications(processed_meds_file)
    removed_count = 0
    
    # Count files before cleaning
    files_before = len([f for f in os.listdir(output_folder) if f.endswith('.json')])
    before_msg = f"[{file_type}] Files before cleaning: {files_before}"
    print(before_msg)
    append_to_log(log_file, before_msg)
    
    # OBJECTIVE: Check each output file for duplicates
    for file in os.listdir(output_folder):
        if not file.endswith('.json'):
            continue
            
        file_path = os.path.join(output_folder, file)
        
        try:
            # Extract medication name based on file type
            if file_type == "csv":
                med_name = extract_medication_name_from_csv(file_path)
            else:
                med_name = extract_medication_name_from_xml(file_path)

            # OBJECTIVE: Remove duplicate files and track new medications
            if med_name and (med_name in processed_medications):
                # This medication has already been processed - remove the duplicate
                os.remove(file_path)
                removed_count += 1
                append_to_log(log_file, f"Removed duplicate: {file_path} - Medication: {med_name}")
            elif med_name:
                # This is a new medication - add it to the tracking file
                save_processed_medication(processed_meds_file, med_name)
                processed_medications.add(med_name)
        except Exception as e:
            # Log errors during processing
            error_msg = f"Error processing {file}: {str(e)}"
            print(error_msg)
            append_to_log(log_file, error_msg)
    
    # OBJECTIVE: Log cleaning results
    files_after = len([f for f in os.listdir(output_folder) if f.endswith('.json')])
    after_msg = f"[{file_type}] Files after cleaning: {files_after}"
    removed_msg = f"[{file_type}] Files removed: {files_before - files_after}"
    
    print(after_msg)
    print(removed_msg)
    append_to_log(log_file, after_msg)
    append_to_log(log_file, removed_msg)
    
    return removed_count

def save_processed_medication(file_path, medication_name):
    """
    Save a medication name to the processed medications file.
    
    Args:
        file_path (str): Path to the processed medications file
        medication_name (str): Name of the medication to save
    """
    # OBJECTIVE: Add this medication to the tracking file
    if not medication_name:
        return
        
    normalized_name = normalize_medication_name(medication_name)
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(f"{normalized_name}\n")

# -----------------------------------------------------------------------------------
# MAIN ENTRY POINT
# -----------------------------------------------------------------------------------

def main():
    """
    Main entry point for the file conversion process.
    
    Initializes the configuration, processes all file types, and outputs a summary.
    """
    # OBJECTIVE: Initialize configuration and process files
    config_loader = ConfigLoader()
    summary = process_file_types(config_loader)
    
    # OBJECTIVE: Output summary to console
    print("\n============================ Processing Summary ============================")
    print(f"Total initial files: {summary['Total initial files']}")
    print(f"Total converted files: {summary['Total converted files']}")
    print(f"Total files before cleaning: {summary['Total files before cleaning']}")
    print(f"Total files after cleaning: {summary['Total files after cleaning']}")
    print(f"Total duplicates removed: {summary['Total duplicates removed']}")
    print("==============================================================================\n")

if __name__ == "__main__":
    main()