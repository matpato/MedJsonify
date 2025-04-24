import os
import json
import xml.etree.ElementTree as ET
from glob import glob
from converter.python_converter import parse_xml_to_json, check_null_fields
from converter.xslt_converter import apply_xslt_to_xml
from converter.csv_converter import convert_csv_to_json
from config_loader import ConfigLoader
import datetime

def normalize_medication_name(name):
    if name:
        return name.lower().strip()
    return None

# -----------------------------------------------------------------------------------

def load_processed_medications(file_path):
    processed = set()
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                med_name = normalize_medication_name(line)
                if med_name:
                    processed.add(med_name)
    return processed

# -----------------------------------------------------------------------------------

def extract_medication_name_from_csv(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return normalize_medication_name(data.get('Proper Name'))
    return None

# -----------------------------------------------------------------------------------

def extract_medication_name_from_xml(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return normalize_medication_name(data.get('name'))
    return None

# -----------------------------------------------------------------------------------

def write_log_summary(log_file_path, summary):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file_path, 'a', encoding='utf-8') as f:
        f.write(f"\n---------------------- Processing Summary [{timestamp}] ----------------------\n")
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

# -----------------------------------------------------------------------------------

def append_to_log(log_file_path, message):
    with open(log_file_path, 'a', encoding='utf-8') as f:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {message}\n")

# -----------------------------------------------------------------------------------

def process_file_types(config_loader):
    log_file = config_loader.get_log_file_path() # missing_fields_log.txt
    unconverted_file = config_loader.get_unconverted_file_path() # unconverted_files.txt
    processed_medications_file = config_loader.get_processed_medications_file_path() # drugs.txt
    processing_summary_file = config_loader.get_summary_file_path() # summary.txt
    conversion_method = config_loader.get_conversion_method()
    file_types = config_loader.get_file_types()
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    os.makedirs(os.path.dirname(unconverted_file), exist_ok=True)
    os.makedirs(os.path.dirname(processed_medications_file), exist_ok=True)

    missing_fields_log = []
    converted_count = 0  
    unconverted_count = 0
    unconverted_files = []
    
    file_counters = {file_type: {'initial': 0, 'converted': 0, 'unconverted': 0, 'skipped': 0, 'removed_duplicates': 0, 
                                'files_before_cleaning': 0, 'files_after_cleaning': 0} for file_type in file_types}
    
    total_counters = {'initial': 0, 'converted': 0, 'unconverted': 0, 'skipped': 0, 'removed_duplicates': 0,
                      'files_before_cleaning': 0, 'files_after_cleaning': 0}

    for file_type in file_types:
        input_folder = config_loader.get_input_folder_for_type(file_type)
        output_folder = config_loader.get_output_folder_for_type(file_type)
        
        if not os.path.exists(output_folder):
            os.makedirs(output_folder, exist_ok=True)
        
        input_files = glob(os.path.join(input_folder, f'*.{file_type}'))
        file_counters[file_type]['initial'] = len(input_files)
        total_counters['initial'] += len(input_files)
        
        process_msg = f"Processing {file_type} files: Found {len(input_files)} files in {input_folder}"
        print(process_msg)
        append_to_log(log_file, process_msg)

        for input_file in input_files:
            output_file = os.path.join(output_folder, os.path.basename(input_file).replace(f'.{file_type}', '.json'))
            try:
                if file_type == 'xml':
                    if conversion_method == 'xslt':
                        xslt_path = os.path.join(os.path.dirname(__file__), '..', 'conversion_xslt.xslt')
                        json_data = apply_xslt_to_xml(xslt_path, input_file)
                    elif conversion_method == 'python':
                        json_data = parse_xml_to_json(input_file)
                    
                    missing_fields = check_null_fields(json_data)
                    if missing_fields:
                        missing_fields_log.append(f"File: {input_file}, Missing fields: {', '.join(missing_fields)}")
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=4, ensure_ascii=False)
                    file_counters[file_type]['converted'] += 1
                    converted_count += 1

                elif file_type in ['csv', 'txt']:
                    result = convert_csv_to_json(input_file, output_folder)
                    if result:
                        file_counters[file_type]['converted'] += 1
                        converted_count += 1
                    else:
                        file_counters[file_type]['unconverted'] += 1
                        unconverted_count += 1
                        unconverted_files.append(input_file)
            except Exception as e:
                file_counters[file_type]['unconverted'] += 1
                unconverted_count += 1
                unconverted_files.append(input_file)
                with open(unconverted_file, 'a', encoding='utf-8') as f:
                    f.write(f"{input_file} - Error: {str(e)}\n")
        
        total_counters['converted'] += file_counters[file_type]['converted']
        total_counters['unconverted'] += file_counters[file_type]['unconverted']

        files_before_cleaning = len(glob(os.path.join(output_folder, '*.json')))
        file_counters[file_type]['files_before_cleaning'] = files_before_cleaning
        total_counters['files_before_cleaning'] += files_before_cleaning
        
        before_cleaning_msg = f"[{file_type}] Files before cleaning duplicates: {files_before_cleaning}"
        print(before_cleaning_msg)
        append_to_log(log_file, before_cleaning_msg)
        
        removed_count = clean_repeated_medications(processed_medications_file, output_folder, file_type, log_file)
        file_counters[file_type]['removed_duplicates'] = removed_count
        total_counters['removed_duplicates'] += removed_count
        
        files_after_clean = len(glob(os.path.join(output_folder, '*.json')))
        file_counters[file_type]['files_after_cleaning'] = files_after_clean
        total_counters['files_after_cleaning'] += files_after_clean
        
        summary_msg = f"[{file_type}] Initial: {file_counters[file_type]['initial']}, Converted: {file_counters[file_type]['converted']}, " \
                      f"Unconverted: {file_counters[file_type]['unconverted']}, Removed duplicates: {removed_count}, " \
                      f"Final count: {files_after_clean}"
        print(summary_msg)
        append_to_log(log_file, summary_msg)

    with open(unconverted_file, 'w', encoding='utf-8') as f:
        for file in unconverted_files:
            f.write(f"{file}\n")
    
    with open(log_file, 'w', encoding='utf-8') as f:
        for log_entry in missing_fields_log:
            f.write(f"{log_entry}\n")

    
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

# -----------------------------------------------------------------------------------

def clean_repeated_medications(processed_meds_file, output_folder, file_type, log_file):
    processed_medications = load_processed_medications(processed_meds_file)
    removed_count = 0
    
    files_before = len([f for f in os.listdir(output_folder) if f.endswith('.json')])
    before_msg = f"[{file_type}] Files before cleaning: {files_before}"
    print(before_msg)
    append_to_log(log_file, before_msg)
    
    for file in os.listdir(output_folder):
        if not file.endswith('.json'):
            continue
            
        file_path = os.path.join(output_folder, file)
        
        try:
            if file_type == "csv":
                med_name = extract_medication_name_from_csv(file_path)
            else:
                med_name = extract_medication_name_from_xml(file_path)

            if med_name and (med_name in processed_medications):
                os.remove(file_path)
                removed_count += 1
                append_to_log(log_file, f"Removed duplicate: {file_path} - Medication: {med_name}")
            elif med_name:
                save_processed_medication(processed_meds_file, med_name)
                processed_medications.add(med_name)
        except Exception as e:
            error_msg = f"Error processing {file}: {str(e)}"
            print(error_msg)
            append_to_log(log_file, error_msg)
    
    files_after = len([f for f in os.listdir(output_folder) if f.endswith('.json')])
    after_msg = f"[{file_type}] Files after cleaning: {files_after}"
    removed_msg = f"[{file_type}] Files removed: {files_before - files_after}"
    
    print(after_msg)
    print(removed_msg)
    append_to_log(log_file, after_msg)
    append_to_log(log_file, removed_msg)
    
    return removed_count

# -----------------------------------------------------------------------------------

def save_processed_medication(file_path, medication_name):
    if not medication_name:
        return
        
    normalized_name = normalize_medication_name(medication_name)
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(f"{normalized_name}\n")

# -----------------------------------------------------------------------------------

def main():
    config_loader = ConfigLoader()
    summary = process_file_types(config_loader)
    
    print("\n============================ Processing Summary ============================")
    print(f"Total initial files: {summary['Total initial files']}")
    print(f"Total converted files: {summary['Total converted files']}")
    print(f"Total files before cleaning: {summary['Total files before cleaning']}")
    print(f"Total files after cleaning: {summary['Total files after cleaning']}")
    print(f"Total duplicates removed: {summary['Total duplicates removed']}")
    print("==============================================================================\n")

if __name__ == "__main__":
    main()