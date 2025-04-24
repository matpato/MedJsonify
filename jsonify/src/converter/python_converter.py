###############################################################################
#                                                                             #  
# @author: Carolina Pereira                                                   #  
# @email: carolinadpereira18@gmail.com                                        #
# @date: 17 Nov 2024                                                          #
# @version: 1.0                                                               #  
# ISEL - Instituto Superior de Engenharia de Lisboa                           #
#                                                                             #
###############################################################################

import os
import json
import xml.etree.ElementTree as ET
from glob import glob

def parse_xml_to_json(xml_file):
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        ns = {'ns': 'urn:hl7-org:v3'}

        def safe_find(element, path, attr=None):
            found = element.find(path, ns)
            if found is not None:
                return found.attrib.get(attr) if attr else ''.join(found.itertext()).strip().replace('\n', ' ')
            return None

        def extract_section(code):
            for section in root.findall(".//ns:section", ns):
                code_element = section.find("ns:code", ns)
                if code_element is not None and code_element.attrib.get("code") == code:
                    all_text = []
                    for element in section.iter():
                        if element.text and element.text.strip():
                            all_text.append(element.text.strip())
                        if element.tail and element.tail.strip():
                            all_text.append(element.tail.strip())

                    return ' '.join(all_text) if all_text else None
            return None
        
        # ----------------------------------------------------------------------------------------
        
        def get_indications():
            indications = extract_section("34067-9")
            result = ""
            if indications:
                result += indications
            return result if result else None

        def get_contraindications():
            contraindications1 = extract_section("34070-3")
            contraindications2 = extract_section("3-3")
            result = ""
            if contraindications1:
                result += contraindications1
            if contraindications2:
                result += contraindications2
            return result if result else None
        
        # ----------------------------------------------------------------------------------------

        def get_warnings_precautions():
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
        
        # ----------------------------------------------------------------------------------------

        def get_adverse_reactions():
            adverse_reactions = extract_section("34084-4")
            result = ""
            if adverse_reactions:
                result += adverse_reactions
            return result if result else None
        
        # ----------------------------------------------------------------------------------------

        def get_name_of_organization():
            return safe_find(root, ".//ns:representedOrganization/ns:name")
        
        # ----------------------------------------------------------------------------------------

        def get_name_of_drug():
            return safe_find(root, ".//ns:manufacturedProduct/ns:name")
        
        # ----------------------------------------------------------------------------------------

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
    
# ------------------------------------------------------------------------------------------------

def check_null_fields(json_data):
    null_fields = []

    def recursive_check(data, parent_key=""):
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{parent_key}.{key}" if parent_key else key
                if value is None:
                    null_fields.append(full_key)
                else:
                    recursive_check(value, full_key)
        elif isinstance(data, list):
            for index, item in enumerate(data):
                recursive_check(item, f"{parent_key}[{index}]")

    recursive_check(json_data)
    return null_fields