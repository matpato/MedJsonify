from pathlib import Path
from jsonifyer import convert_txt, convert_csv, convert_xml
import os
import json
import xml.etree.ElementTree as ET
import sys


def convert_all_files():
        BASE_DIR = Path("/opt/airflow/dags/jsonify/src")
        input_folder = BASE_DIR / 'types'
        output_folder = BASE_DIR / 'json'
        
        for dir_type in ['xml_files', 'csv_files', 'txt_files']:
            os.makedirs(output_folder / dir_type, exist_ok=True)
        
        repeated_files = {
            'xml_files': BASE_DIR / 'xml_processed.txt',
            'csv_files': BASE_DIR / 'csv_processed.txt',
            'txt_files': BASE_DIR / 'txt_processed.txt'
        }
        
        # Initialize tracking files if they don't exist
        for file_path in repeated_files.values():
            if not file_path.exists():
                file_path.touch()
        
        #######################################################################################################

        xml_input_dir = input_folder / 'xml_files'
        xml_output_dir = output_folder / 'xml_files'

        if xml_input_dir.exists():
            print(f"INFO: Processing XML files in {xml_input_dir}...")
            try:
                ns = {'': 'urn:hl7-org:v3'}
                fields = {
                    'id': './/id/@root',
                    'code.code': './/code/@code',
                    'code.codeSystem': './/code/@codeSystem',
                    'code.displayName': './/code/@displayName',
                    'organization': './/author/assignedEntity/representedOrganization/name',
                    'name': './/component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct/name',
                    'effectiveTime': './/effectiveTime/@value',
                    'ingredients.name': './/component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct/ingredient/ingredientSubstance/name',
                    'ingredients.code': './/component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct/ingredient/ingredientSubstance/code/@code',
                }
                section_codes = {
                    'indications': '34067-9',
                    'contraindications': '34068-7',
                    'warningsAndPrecautions': '34069-5', 
                    'adverseReactions': '34070-3'
                }
                pairs = {
                    'ingredients.name': [
                        './/component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct/ingredient/ingredientSubstance',
                        'name'
                    ],
                    'ingredients.code': [
                        './/component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct/ingredient/ingredientSubstance',
                        'code/@code'
                    ],
                }

                result = convert_xml(
                    directory_path=str(xml_input_dir),
                    repeated_path=str(repeated_files['xml_files']),
                    repeated_item='name',
                    output_path=str(xml_output_dir),
                    converter="python",
                    field_map=fields,
                    extra_fields=section_codes,
                    namespaces=ns,
                    pairs=pairs,
                    root_tag="document"
                )
                
                if isinstance(result, dict) and 'message' in result:
                    print(f"✓ {result['message']}")
                else:
                    print("✓ XML files processed")
                    
            except Exception as e:
                print(f"✗ Error processing XML files: {str(e)}")
                raise

        print("INFO: Finished XML file processing. Starting CSV file processing...")

        ########################################################################################################

        csv_input_dir = input_folder / 'csv_files'
        csv_output_dir = output_folder / 'csv_files'
        
        if csv_input_dir.exists():
            print(f"INFO: Processing CSV files in {csv_input_dir}...")
            for filename in os.listdir(csv_input_dir):
                if not filename.lower().endswith('.csv'):
                    continue
                filepath = csv_input_dir / filename
                print(f"INFO: Attempting to process CSV: {filename}...")

                try:
                    print(f"INFO: Calling convert_csv with repeated_path: {repeated_files['csv_files']}, repeated_item: Proper Name")
                    result = convert_csv(
                        file_path=str(filepath),
                        output_path=str(csv_output_dir),
                        repeated_path=str(repeated_files['csv_files']),
                        repeated_item='Proper Name', 
                        skiprows=3
                    )
                    print(f"INFO: Finished processing CSV: {filename}. Result: {result}")
                    
                    if isinstance(result, dict) and 'message' in result:
                        print(f"✓ {result['message']}")
                    else:
                        print(f"✓ {filename} processed")

                except Exception as e:
                    print(f"✗ Error processing {filename}: {str(e)}")
                    raise

        print("INFO: Finished CSV file processing. Starting TXT file processing...")

        ########################################################################################################

        txt_input_dir = input_folder / 'txt_files'
        txt_output_dir = output_folder / 'txt_files'
        
        if txt_input_dir.exists():
            print(f"INFO: Processing TXT files in {txt_input_dir}...")
            for filename in os.listdir(txt_input_dir):
                if not filename.lower().endswith('.txt'):
                    continue
                    
                filepath = txt_input_dir / filename
                print(f"INFO: Attempting to process TXT: {filename}...")
                
                try:
                    print(f"INFO: Calling convert_txt with repeated_path: {repeated_files['txt_files']}, repeated_item: Ingredient")
                    result = convert_txt(
                        file_path=str(filepath),
                        output_path=str(txt_output_dir),
                        repeated_path=str(repeated_files['txt_files']),
                        repeated_item='Ingredient', 
                        delimiter='~'
                    )
                    print(f"INFO: Finished processing TXT: {filename}. Result: {result}")
                    
                    if isinstance(result, dict) and 'message' in result:
                        print(f"✓ {result['message']}")
                    else:
                        print(f"✓ {filename} processed")

                except Exception as e:
                    print(f"✗ Error processing {filename}: {str(e)}")
                    raise

        print("All file conversions attempted.")
        return 0


