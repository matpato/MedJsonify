###############################################################################
#                                                                             #  
# @file: xslt_converter.py                                                    #  
# @description: Converts XML files to JSON using XSLT transformations         #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This module provides functionality to convert XML files to JSON format      #
# using XSLT transformation templates. It includes tools to process entire    #
# directories of XML files, track conversion statistics, and log issues       #
# such as missing fields or failed conversions.                               #
#                                                                             #  
###############################################################################

import os
import json
from lxml import etree
from glob import glob

def apply_xslt_to_xml(xslt_path, xml_path):
    """
    Transform an XML file to JSON using an XSLT template.
    
    This function applies an XSLT transformation to an XML file,
    converting it to a JSON-compatible Python dictionary.
    
    Args:
        xslt_path (str): Path to the XSLT transformation file.
        xml_path (str): Path to the XML file to be transformed.
        
    Returns:
        dict: The transformed data as a Python dictionary.
        
    Raises:
        ValueError: If an error occurs during transformation.
    """
    try:
        # OBJECTIVE: Set up secure XML parsing
        # Configure parser with security settings to prevent XXE attacks
        parser = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)
        
        # OBJECTIVE: Load and prepare the XML and XSLT files
        # Load the XSLT transformation template
        xslt_tree = etree.parse(xslt_path, parser) 
        transform = etree.XSLT(xslt_tree)
        
        # Load the XML file to be transformed
        xml_tree = etree.parse(xml_path, parser) 
        
        # OBJECTIVE: Apply the XSLT transformation to the XML
        # Transform the XML using the XSLT template and convert to JSON
        result_tree = transform(xml_tree)
        return json.loads(str(result_tree))
    except Exception as e:
        raise ValueError(f"Error processing {xml_path} with XSLT: {e}")
    
def check_null_and_empty_fields(json_data):
    """
    Recursively check for null or empty fields in a JSON structure.
    
    This function identifies and lists all fields with null values or empty lists
    in a JSON object, including nested objects and arrays.
    
    Args:
        json_data (dict): The JSON data structure to check.
        
    Returns:
        list: A list of field paths that have null or empty values.
    """
    null_or_empty_fields = []

    # OBJECTIVE: Recursively traverse JSON structure to find null or empty values
    def recursive_check(data, parent_key=""):
        """
        Recursively check data structure for null or empty fields.
        
        Args:
            data: The data structure to check (dict, list, or value)
            parent_key: The current path in the JSON structure
        """
        if isinstance(data, dict):
            # For dictionaries, check each key-value pair
            for key, value in data.items():
                full_key = f"{parent_key}.{key}" if parent_key else key
                if value is None or (isinstance(value, list) and not value):
                    null_or_empty_fields.append(full_key)
                else:
                    recursive_check(value, full_key)
        elif isinstance(data, list):
            # For lists, check each item with its index
            for index, item in enumerate(data):
                recursive_check(item, f"{parent_key}[{index}]")

    # Start the recursive check from the root
    recursive_check(json_data)
    return null_or_empty_fields

def process_folder_with_xslt(input_folder, output_folder, log_file, unconverted_log_file, xslt_path):
    """
    Process a folder of XML files, converting them to JSON using XSLT.
    
    This function handles the batch conversion of XML files to JSON, tracks statistics,
    and logs issues such as missing fields or failed conversions.
    
    Args:
        input_folder (str): Path to the folder containing XML files.
        output_folder (str): Path where JSON files will be saved.
        log_file (str): Path for the log file tracking missing fields.
        unconverted_log_file (str): Path for the log file tracking failed conversions.
        xslt_path (str): Path to the XSLT transformation file.
    """
    # OBJECTIVE: Create output directory if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # OBJECTIVE: Find all XML files in the input folder
    xml_files = glob(os.path.join(input_folder, '*.xml'))
    
    # OBJECTIVE: Initialize tracking variables
    missing_fields_log = []  # Track files with missing fields
    unconverted_files = []   # Track files that failed to convert
    converted_count = 0      # Count successfully converted files

    # OBJECTIVE: Process each XML file in the input folder
    for xml_file in xml_files:
        try:
            # Convert the XML file to JSON using XSLT
            json_data = apply_xslt_to_xml(xslt_path, xml_file)
            
            # Generate output filename by replacing .xml extension with .json
            output_file = os.path.join(output_folder, os.path.basename(xml_file).replace('.xml', '.json'))

            # OBJECTIVE: Save the converted JSON data to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=4, ensure_ascii=False)

            print(f"Converted: {xml_file} -> {output_file}")
            converted_count += 1

            # OBJECTIVE: Check for and log missing or empty fields
            null_or_empty_fields = check_null_and_empty_fields(json_data)
            if null_or_empty_fields:
                missing_fields_log.append({
                    "file": os.path.basename(xml_file),
                    "missing_fields": null_or_empty_fields
                })

        except Exception as e:
            # Log conversion failures
            print(f"Error processing {xml_file}: {e}")
            unconverted_files.append(os.path.basename(xml_file))

    # OBJECTIVE: Write the missing fields log
    with open(log_file, 'w', encoding='utf-8') as log:
        log.write(f"-------------------------------------------------------------------------\n")
        log.write(f"Total JSON files converted: {converted_count}\n")
        log.write(f"-------------------------------------------------------------------------\n\n")

        log.write("Files with missing fields:\n")
        for entry in missing_fields_log:
            log.write(f"File: {entry['file']}\n")
            log.write("Missing fields:\n")
            for field in entry['missing_fields']:
                log.write(f"  - {field}\n")
            log.write("\n")

    # OBJECTIVE: Write the unconverted files log
    with open(unconverted_log_file, 'w', encoding='utf-8') as unconverted_log:
        unconverted_log.write(f"-------------------------------------------------------------------------\n")
        unconverted_log.write("Unconverted files:\n")

        for file in unconverted_files:
            unconverted_log.write(f"  - {file}\n")
    
    # OBJECTIVE: Output summary statistics
    print(f"Missing fields in {log_file}")
    print(f"Unconverted files in {unconverted_log_file}")
    print(f"Total of JSON files converted: {converted_count}")
    print(f"Total of unconverted files: {len(unconverted_files)}")