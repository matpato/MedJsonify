import os
import json
from lxml import etree
from glob import glob

def apply_xslt_to_xml(xslt_path, xml_path):
    try:
        # Configurar o parser para desativar DTDs e conexões de rede
        parser = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)
        
        # Carregar os arquivos XML e XSLT
        xslt_tree = etree.parse(xslt_path, parser) 
        transform = etree.XSLT(xslt_tree)
        xml_tree = etree.parse(xml_path, parser) 
        
        # Transformar o XML com o XSLT
        result_tree = transform(xml_tree)
        return json.loads(str(result_tree))
    except Exception as e:
        raise ValueError(f"Erro ao processar {xml_path} com XSLT: {e}")
    
# ----------------------------------------------------------------------------------------

def check_null_and_empty_fields(json_data):
    null_or_empty_fields = []

    def recursive_check(data, parent_key=""):
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{parent_key}.{key}" if parent_key else key
                if value is None or (isinstance(value, list) and not value):
                    null_or_empty_fields.append(full_key)
                else:
                    recursive_check(value, full_key)
        elif isinstance(data, list):
            for index, item in enumerate(data):
                recursive_check(item, f"{parent_key}[{index}]")

    recursive_check(json_data)
    return null_or_empty_fields

# ----------------------------------------------------------------------------------------

def process_folder_with_xslt(input_folder, output_folder, log_file, unconverted_log_file, xslt_path):
    os.makedirs(output_folder, exist_ok=True)
    xml_files = glob(os.path.join(input_folder, '*.xml'))
    missing_fields_log = []
    unconverted_files = []
    converted_count = 0

    for xml_file in xml_files:
        try:
            json_data = apply_xslt_to_xml(xslt_path, xml_file)
            output_file = os.path.join(output_folder, os.path.basename(xml_file).replace('.xml', '.json'))

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=4, ensure_ascii=False)

            print(f"Converted: {xml_file} -> {output_file}")
            converted_count += 1

            null_or_empty_fields = check_null_and_empty_fields(json_data)
            if null_or_empty_fields:
                missing_fields_log.append({
                    "file": os.path.basename(xml_file),
                    "missing_fields": null_or_empty_fields
                })

        except Exception as e:
            print(f"Erro ao processar {xml_file}: {e}")
            unconverted_files.append(os.path.basename(xml_file))

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

    with open(unconverted_log_file, 'w', encoding='utf-8') as unconverted_log:
        unconverted_log.write(f"-------------------------------------------------------------------------\n")
        unconverted_log.write("Unconverted files:\n")

        for file in unconverted_files:
            unconverted_log.write(f"  - {file}\n")
    
    print(f"Missing fields in {log_file}")
    print(f"Unconverted files in {unconverted_log_file}")
    print(f"Total of JSON files converted: {converted_count}")
    print(f"Total of unconverted files: {len(unconverted_files)}")