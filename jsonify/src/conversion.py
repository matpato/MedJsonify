from pathlib import Path
from jsonifyer import convert_file, convert_csv, convert_xml
import os
import json
import xml.etree.ElementTree as ET

def convert_all_files():
    BASE_DIR = Path("/opt/airflow/dags/jsonify/src")
    input_folder = BASE_DIR / 'types'
    output_folder = BASE_DIR / 'json'

    for dir_type in ['xml_files', 'csv_files', 'txt_files']:
        os.makedirs(output_folder / dir_type, exist_ok=True)

    for dir_type in ['xml_files', 'csv_files', 'txt_files']:
        input_dir = os.path.join(input_folder, dir_type)
        output_dir = os.path.join(output_folder, dir_type)
        if not os.path.exists(input_dir):
            continue
        for filename in os.listdir(input_dir):
            filepath = os.path.join(input_dir, filename)
            if filename.lower().endswith('.xml'):
                result = convert_xml(
                    file_path=filepath,
                    fields=[
                        './/id/@root',
                        './/code/@code',
                        './/code/@codeSystem',
                        './/code/@displayName',
                        './/author/assignedEntity/representedOrganization/name',
                        './/effectiveTime/@value',
                        './/component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct/name',
                    ],
                    converter="python",
                    namespaces={"ns": "urn:hl7-org:v3"},
                    root_tag="document"
                )

                tree = ET.parse(filepath)
                root = tree.getroot()
                ns = {'': 'urn:hl7-org:v3'}

                ingredients = []
                manufactured_products = root.findall('.//component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct', ns)
                for product in manufactured_products:
                    ing_elems = product.findall('ingredient', ns)
                    for ing in ing_elems:
                        sub = ing.find('ingredientSubstance', ns)
                        if sub is not None:
                            ing_name = ''.join(sub.find('name', ns).itertext()).strip() if sub.find('name', ns) is not None else None
                            ing_code = sub.find('code', ns).attrib.get('code') if sub.find('code', ns) is not None else None
                            if {'name': ing_name, 'code': ing_code} not in ingredients:
                                ingredients.append({'name': ing_name, 'code': ing_code})
                result['ingredients'] = ingredients

                def extract_section_text(code_value):
                    for section in root.findall('.//section', ns):
                        code = section.find('code', ns)
                        if code is not None and code.attrib.get('code') == code_value:
                            text_elem = section.find('text', ns)
                            if text_elem is not None and ''.join(text_elem.itertext()).strip():
                                return ''.join(text_elem.itertext()).strip()
                            excerpt_elem = section.find('excerpt', ns)
                            if excerpt_elem is not None:
                                return ' '.join([t.strip() for t in excerpt_elem.itertext() if t.strip()])
                    return None

                result['indications'] = extract_section_text('34067-9')
                result['contraindications'] = extract_section_text('34068-7')
                result['warningsAndPrecautions'] = extract_section_text('34069-5')
                result['adverseReactions'] = extract_section_text('34070-3')

                output_file = os.path.join(output_dir, f"{Path(filename).stem}.json")
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=4, ensure_ascii=False)
                print(f"Arquivo {filename} convertido e salvo em {output_file}")
            elif filename.lower().endswith('.csv'):
                result = convert_csv(filepath, skiprows=3, output_path=output_dir)
                if isinstance(result, dict) and 'message' in result:
                    print(result['message'])
                elif isinstance(result, list):
                    for index, item in enumerate(result):
                        cleaned_item = {k: v for k, v in item.items() if v is not None}
                        if cleaned_item:
                            output_file = os.path.join(output_dir, f"{Path(filename).stem}_{index}.json")
                            with open(output_file, 'w', encoding='utf-8') as f:
                                json.dump(cleaned_item, f, indent=4, ensure_ascii=False)
                            print(f"Linha {index} do arquivo {filename} convertida e salva em {output_file}")
                else:
                    output_file = os.path.join(output_dir, f"{Path(filename).stem}.json")
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=4, ensure_ascii=False)
                    print(f"Arquivo {filename} convertido e salvo em {output_file}")
            elif filename.lower().endswith('.txt'):
                result = convert_file(filepath, file_type="txt", output_path=output_dir)
                if isinstance(result, dict) and 'message' in result:
                    print(result['message'])
                elif isinstance(result, list):
                    for index, item in enumerate(result):
                        output_file = os.path.join(output_dir, f"{Path(filename).stem}_{index}.json")
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(item, f, indent=4, ensure_ascii=False)
                        print(f"Linha {index} do arquivo {filename} convertida e salva em {output_file}")
                else:
                    output_file = os.path.join(output_dir, f"{Path(filename).stem}.json")
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=4, ensure_ascii=False)
                    print(f"Arquivo {filename} convertido e salvo em {output_file}")
            else:
                continue 