###############################################################################
#                                                                             #  
# @file: python_converter.py                                                  #  
# @description: Converts XML files to JSON using Python's ElementTree         #
# @date: May 2025 (Updated from Nov 2024)                                     #
# @version: 2.0                                                               #  
#                                                                             #  
# This module provides functions to parse pharmaceutical XML files and        #
# convert them to JSON format. It extracts structured data including drug     #
# information, indications, contraindications, warnings, and adverse          #
# reactions from HL7-compliant XML documents.                                 #
#                                                                             #  
###############################################################################

import os
import json
import xml.etree.ElementTree as ET
from glob import glob

def parse_xml_to_json(xml_file):
    """
    Parse an XML file and convert it to a JSON-compatible dictionary.
    
    This function extracts structured data from HL7-compliant XML files,
    organizing the data into a standardized dictionary format.
    
    Args:
        xml_file (str): Path to the XML file to be parsed.
        
    Returns:
        dict: A dictionary containing structured data from the XML file.
        
    Raises:
        ValueError: If an error occurs during parsing or processing.
    """
    try:
        # OBJECTIVE: Parse the XML file and set up the namespace
        tree = ET.parse(xml_file)
        root = tree.getroot()
        ns = {'ns': 'urn:hl7-org:v3'}  # HL7 namespace

        # OBJECTIVE: Define helper functions for safe XML element extraction
        def safe_find(element, path, attr=None):
            """
            Safely extract text or attribute from an XML element.
            
            Args:
                element: The parent XML element to search within
                path: XPath to the target element
                attr: Optional attribute name to extract
                
            Returns:
                str or None: The extracted text or attribute value, or None if not found
            """
            found = element.find(path, ns)
            if found is not None:
                return found.attrib.get(attr) if attr else ''.join(found.itertext()).strip().replace('\n', ' ')
            return None

        # OBJECTIVE: Define function to extract content from a specific section
        def extract_section(code):
            """
            Extract all text content from a section with the specified code.
            
            Args:
                code: The section code to find (e.g., "34067-9" for indications)
                
            Returns:
                str or None: The concatenated text from the section, or None if not found
            """
            for section in root.findall(".//ns:section", ns):
                code_element = section.find("ns:code", ns)
                if code_element is not None and code_element.attrib.get("code") == code:
                    all_text = []
                    # Extract all text from the section, including element text and tail
                    for element in section.iter():
                        if element.text and element.text.strip():
                            all_text.append(element.text.strip())
                        if element.tail and element.tail.strip():
                            all_text.append(element.tail.strip())

                    return ' '.join(all_text) if all_text else None
            return None
        
        # ----------------------------------------------------------------------------------------
        # OBJECTIVE: Extract specific sections of the document based on section codes
        
        def get_indications():
            """
            Extract drug indications from the XML document.
            """
            indications = extract_section("34067-9")  # Standard code for indications
            result = ""
            if indications:
                result += indications
            return result if result else None

        def get_contraindications():
            """
            Extract drug contraindications from the XML document.
            """
            # Check multiple possible section codes for contraindications
            contraindications1 = extract_section("34070-3")
            contraindications2 = extract_section("3-3")
            result = ""
            if contraindications1:
                result += contraindications1
            if contraindications2:
                result += contraindications2
            return result if result else None
        
        def get_warnings_precautions():
            """
            Extract warnings and precautions from the XML document.
            """
            # Check multiple possible section codes for warnings and precautions
            warnings_and_precautions = extract_section("43685-7")
            warnings = extract_section("34071-1")
            precautions = extract_section("42232-9")
            result = ""
            if warnings_and_precautions:
                result += warnings_and_precautions
            if warnings:
                result += warnings
            if precautions:
                result += precautions
            return result if result else None
        
        def get_adverse_reactions():
            """
            Extract adverse reactions from the XML document.
            """
            adverse_reactions = extract_section("34084-4")  # Standard code for adverse reactions
            result = ""
            if adverse_reactions:
                result += adverse_reactions
            return result if result else None
               
        def get_name_of_organization():
            """
            Extract the manufacturer organization name from the XML document.
            """
            return safe_find(root, ".//ns:representedOrganization/ns:name")
             
        def get_name_of_drug():
            """
            Extract the drug name from the XML document.
            """
            return safe_find(root, ".//ns:manufacturedProduct/ns:name")
        
        # ----------------------------------------------------------------------------------------
        # OBJECTIVE: Construct the complete JSON structure from extracted data
        
        data = {
            "id": safe_find(root, 'ns:id', 'root'),
            "code": {
                "code": safe_find(root, 'ns:code', 'code'),
                "codeSystem": safe_find(root, 'ns:code', 'codeSystem'),
                "displayName": safe_find(root, 'ns:code', 'displayName'),
            },
            "name": get_name_of_drug(),
            "organization": get_name_of_organization(),
            "effectiveTime": safe_find(root, 'ns:effectiveTime', 'value'),
            "ingredients": [
                {
                    "name": safe_find(ingr, 'ns:ingredientSubstance/ns:name'),
                    "code": safe_find(ingr, 'ns:ingredientSubstance/ns:code', 'code')
                }
                for ingr in root.findall('.//ns:ingredient', ns)
            ],
            "indications": get_indications(),
            "contraindications": get_contraindications(),
            "warningsAndPrecautions": get_warnings_precautions(),
            "adverseReactions": get_adverse_reactions()
        }

        # OBJECTIVE: Remove duplicate ingredients by name and code
        unique_ingredients = []
        seen = set()
        for ingredient in data["ingredients"]:
            if (ingredient["name"], ingredient["code"]) not in seen:
                unique_ingredients.append(ingredient)
                seen.add((ingredient["name"], ingredient["code"]))
        data["ingredients"] = unique_ingredients

        return data
    except Exception as e:
        raise ValueError(f"Error processing file {xml_file}: {e}")
    

def check_null_fields(json_data):
    """
    Recursively check for null fields in a JSON structure.
    
    This function identifies and lists all fields with null values in a JSON object,
    including nested objects and arrays.
    
    Args:
        json_data (dict): The JSON data structure to check
        
    Returns:
        list: A list of field paths that have null values
    """
    null_fields = []

    # OBJECTIVE: Recursively traverse JSON structure to find null values
    def recursive_check(data, parent_key=""):
        """
        Recursively check data structure for null fields.
        
        Args:
            data: The data structure to check (dict, list, or value)
            parent_key: The current path in the JSON structure
        """
        if isinstance(data, dict):
            # For dictionaries, check each key-value pair
            for key, value in data.items():
                full_key = f"{parent_key}.{key}" if parent_key else key
                if value is None:
                    null_fields.append(full_key)
                else:
                    recursive_check(value, full_key)
        elif isinstance(data, list):
            # For lists, check each item with its index
            for index, item in enumerate(data):
                recursive_check(item, f"{parent_key}[{index}]")

    # Start the recursive check from the root
    recursive_check(json_data)
    return null_fields