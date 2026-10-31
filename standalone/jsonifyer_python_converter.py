import os
import json
import csv
import re
import logging
import xml.etree.ElementTree as ET
from glob import glob
from typing import Dict, List, Optional, Union, Any
from pathlib import Path
from .xslt_converter import apply_xslt_to_xml

logger = logging.getLogger(__name__)


def _pair_value(element, path, namespaces):
    """
    Value of `path` relative to `element`, for the `pairs` option:
      '@attr'              attribute of the element itself  (e.g. '@classCode')
      'a/b/@attr'          attribute of a child element      (e.g. 'ingredientSubstance/code/@code')
      'a/b'                text of a child element           (e.g. 'ingredientSubstance/name')
    """
    if path.startswith('@'):
        return element.attrib.get(path[1:])
    if '/@' in path:
        child_path, attr = path.rsplit('/@', 1)
        child = element.find(child_path, namespaces)
        return child.attrib.get(attr) if child is not None else None
    child = element.find(path, namespaces)
    return ''.join(child.itertext()).strip() if child is not None else None

def _full_text(element):
    """
    Full text of an element, including the text inside child elements
    (e.g. a title with <sup>®</sup> or <br/>). element.text alone stops at the
    first child, which left 427 of 1,645 SPL titles empty. For an element
    without children the result is the same as element.text.strip().
    """
    if element is None:
        return None
    if len(element) == 0:                       # no children: exactly as before
        return element.text.strip() if element.text else ''
    parts = []

    def walk(el):
        if el.text:
            parts.append(el.text)
        for child in el:
            if child.tag.split('}')[-1] == 'br':  # line break -> space
                parts.append(' ')
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(element)
    return re.sub(r'\s+', ' ', ''.join(parts)).strip()


def set_nested_value(d, keys, value):
    # Handles nested dictionary creation with array support
    # For keys ending with '[]', creates or appends to arrays
    for k in keys[:-1]:
        if k.endswith('[]'):
            k = k[:-2]
            d = d.setdefault(k, [])
            if not d or not isinstance(d[-1], dict):
                d.append({})
            d = d[-1]
        else:
            d = d.setdefault(k, {})
    if keys[-1].endswith('[]'):
        k = keys[-1][:-2]
        d.setdefault(k, []).append(value)
    else:
        d[keys[-1]] = value

def parse_xml_to_json(
    xml_file: str,
    repeated_file: str = None,
    field_map: Optional[Dict[str, str]] = None,
    fields: Optional[List[str]] = None,
    namespaces: Optional[Dict[str, str]] = None,
    root_tag: Optional[str] = None,
    extra_fields: Optional[Dict[str, str]] = None,
    pairs: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:

    # Parse XML and get root element
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Extract default namespace from root tag if present
    default_ns = root.tag.split('}')[0].strip('{') if '}' in root.tag else None
    
    ns_prefix = 'ns'
    extra_ns = namespaces
    if default_ns:
        namespaces = {ns_prefix: default_ns}
        
    def add_prefix(xpath):
        # Adds namespace prefix to XPath expressions when default namespace is present
        if default_ns:
            parts = xpath.split('/')
            new_parts = []
            for part in parts:
                if part and not part.startswith('.') and not part.startswith('@') and ':' not in part:
                    if part.startswith('*'):
                        new_parts.append(part)
                    else:
                        new_parts.append(f'{ns_prefix}:{part}')
                else:
                    new_parts.append(part)
            return '/'.join(new_parts)
        return xpath
    
    # Handle custom root tag if specified
    if root_tag:
        root_local = root.tag.split('}')[-1] if '}' in root.tag else root.tag
        if root_local.strip().lower() != root_tag.strip().lower():
            if default_ns:
                root = root.find(f'.//{{{default_ns}}}{root_tag.strip()}')
            else:
                root = root.find(f'.//{root_tag.strip()}')
            if root is None:
                return {}
    
    def safe_find(element, xpath):
        # Safely find elements using XPath with namespace support
        try:
            xpath = add_prefix(xpath)
            if not xpath.startswith('.') and not xpath.startswith('/'):
                xpath = './' + xpath
            result = element.find(xpath, namespaces)
            return result
        except Exception as e:
            return None
    
    def safe_findall(element, xpath):
        # Find all matching elements and handle duplicates
        try:
            xpath = add_prefix(xpath)
            if not xpath.startswith('.') and not xpath.startswith('/'):
                xpath = './' + xpath
            lst = element.findall(xpath, namespaces)
            # If all elements have same text, return single element
            lst_to_compare = [_full_text(el) for el in lst]
            if all(txt == lst_to_compare[0] for txt in lst_to_compare):
                lst = lst[0]
            else:
                # Remove duplicates while preserving order
                s = set()
                lst_to_ret = []
                for el in lst:
                    if _full_text(el) not in s:
                        s.add(_full_text(el))
                        lst_to_ret.append(el)
                lst = lst_to_ret
            return lst
        except Exception as e:
            print("BATATOLAS" + str(e))
            return []
    
    def extract_element_data(element):
        # Recursively extract data from XML element including attributes and nested elements
        if element is None:
            return None
            
        result = {}
        
        # Extract attributes
        for key, value in element.attrib.items():
            result[key] = value
            
        # Extract text content if present
        if element.text and element.text.strip():
            result['text'] = element.text.strip()
            
        # Process child elements
        for child in element:
            child_data = extract_element_data(child)
            if child_data:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag in result:
                    if not isinstance(result[tag], list):
                        result[tag] = [result[tag]]
                    result[tag].append(child_data)
                else:
                    result[tag] = child_data
                    
        return result

    def extract_section_text(code_value):
        # Extract text content from specific section by code value
        for section in root.findall('.//section', extra_ns):
            code = section.find('code', extra_ns)
            if code is not None and code.attrib.get('code') == code_value:
                text_elem = section.find('text', extra_ns)
                if text_elem is not None and ''.join(text_elem.itertext()).strip():
                    return ''.join(text_elem.itertext()).strip()
                excerpt_elem = section.find('excerpt', extra_ns)
                if excerpt_elem is not None:
                    return ' '.join([t.strip() for t in excerpt_elem.itertext() if t.strip()])
        return None
    
    result = {}
    
    # Process field mappings if provided
    if field_map:
        for field, xpath in field_map.items():
            if isinstance(xpath, list):
                # Handle multiple XPath expressions for a single field
                values = []
                for path in xpath:
                    elements = safe_findall(root, path)
                    for element in elements:
                        if element is not None and _full_text(element):
                            values.append(_full_text(element))
                
                if values:
                    if '.' in field:
                        # Handle nested field structure
                        parts = field.split('.')
                        current = result
                        for part in parts[:-1]:
                            if part not in current:
                                current[part] = {}
                            current = current[part]
                        current[parts[-1]] = values
                    else:
                        result[field] = values
            elif '@' in xpath:
                # Handle attribute extraction
                base_path, attr = xpath.rsplit('@', 1)
                base_path = base_path.rstrip('/').strip()
                attr = attr.strip()
                element = safe_find(root, base_path)

                if element is not None and attr in element.attrib:
                    if '.' in field:
                        tag = field.split('.')[0]
                        tagg = field.split('.')[-1]
                        if isinstance(element, list):
                            result[tag] = []
                            for el in element:
                                if isinstance(el, ET.Element):
                                    result[tag].append({str(tagg): _full_text(el) or None})
                                else:
                                    result[tag].append({str(tagg): el})
                    else:
                        result[field] = element.attrib[attr]
            else:
                # Handle regular element extraction
                element = safe_findall(root, xpath)
                if element is not None:
                    if '.' in field:
                        tag = field.split('.')[0]
                        tagg = field.split('.')[-1]
                        if isinstance(element, list):
                            result[tag] = []
                            for el in element:
                                if isinstance(el, ET.Element):
                                    result[tag].append({str(tagg): _full_text(el) or None})
                                else:
                                    result[tag].append({str(tagg): el})
                    else:
                        tag = xpath.split('/')[-1]
                        if isinstance(element, list):
                            result[field] = []
                            for el in element:
                                result[field].append({str(tag): _full_text(el) or None})
                        else:
                            result[field] = _full_text(element) or None
            
            # Process extra fields if specified
            if extra_fields:
                for field_name, code_value in extra_fields.items():
                    section_text = extract_section_text(code_value)
                    if section_text:
                        result[field_name] = section_text

            # Process paired fields if specified
            if pairs:
                tag = list(pairs.keys())[0].split(".")[0]
                tagg = [pr.split(".")[-1] for pr in list(pairs.keys())]
                result[tag] = []
                for xpquery in pairs.values():
                    generic_elem = root.findall(xpquery[0], extra_ns)
                    for sub in generic_elem:
                        dict_to_append = {}
                        for alpha_i, alpha in enumerate([x[-1] for x in list(pairs.values())]):
                            dict_to_append[tagg[alpha_i]] = _pair_value(sub, alpha, extra_ns)
                        result[tag].append(dict_to_append)
                # Remove duplicates while preserving order
                s = set()
                lst_to_ret = []
                for el in result[tag]:
                    if el[tagg[0]] not in s:
                        s.add(el[tagg[0]])
                        lst_to_ret.append(el)
                result[tag] = lst_to_ret

    elif fields:
        # Process simple field list if no field map provided
        for xpath in fields:
            if '@' in xpath:
                base_path, attr = xpath.rsplit('@', 1)
                base_path = base_path.rstrip('/').strip()
                attr = attr.strip()
                element = safe_find(root, base_path)
                if element is not None and attr in element.attrib:
                    result[attr] = element.attrib[attr]
            else:
                element = safe_find(root, xpath)
                if element is not None:
                    tag = xpath.split('/')[-1]
                    if len(element) > 0:
                        result[tag] = extract_element_data(element)
                    else:
                        result[tag] = _full_text(element) or None
    
    else:
        # If no field specifications, extract all data
        result = extract_element_data(root)
    
    return result

def convert_csv(
    input_file: str,
    output_dir: str,
    skiprows: int = 0,
    field_map: Optional[Dict[str, int]] = None
) -> List[str]:
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    created_files = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        # Skip header rows if specified
        for _ in range(skiprows):
            next(reader)
        
        # Process each row
        for i, row in enumerate(reader):
            if not row or not any(row):  # Skip empty rows
                continue
                
            record = {}
            if field_map:
                # Map fields according to provided mapping
                for field_name, col_idx in field_map.items():
                    if col_idx < len(row):
                        value = row[col_idx].strip()
                        if value:  # Only include non-empty values
                            record[field_name] = value
            else:
                # Use default column names if no mapping provided
                record = {f"column_{i}": value.strip() for i, value in enumerate(row) if value.strip()}
            
            if record and len(record) > 1:  # Only create file if record has multiple fields
                output_file = output_path / f"record_{i+1}.json"
                with open(output_file, 'w', encoding='utf-8') as out_f:
                    json.dump(record, out_f, indent=4, ensure_ascii=False)
                created_files.append(str(output_file))
    
    print(f"Created {len(created_files)} JSON files in {output_dir}")
    return created_files

def check_null_fields(json_data: Dict) -> List[str]:
    # Recursively check for null values in JSON structure
    null_fields = []
    
    def recursive_check(data: Any, parent_key: str = "") -> None:
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

class PythonConverter:
    def convert_xml_structured(self, input_file: str, output_dir: str, field_map: Dict[str, str], namespaces: Optional[Dict[str, str]] = None) -> None:
        # Convert XML to JSON and save to file
        result = parse_xml_to_json(input_file, field_map=field_map, namespaces=namespaces)
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, os.path.splitext(os.path.basename(input_file))[0] + '.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)