"""
Count, per source, what the jsonify pipeline does with each input record,
for the "Conversion results" table of the paper.

It reproduces the decisions made by jsonifyer 0.1.10 (convert_xml /
convert_csv / convert_txt) with the same arguments as the Airflow DAG,
but it only counts: it writes no JSON and does not touch the state files
or the input files.

Run it on the May 2025 input folders, e.g.

    python conversion_stats.py /data/may2025_input
    python conversion_stats.py --ini /opt/airflow/dags/jsonify/jsonify.ini
    python conversion_stats.py /data/may2025_input --out-dir results

It saves two files (and prints the first one):
    conversion_results.txt  the LaTeX table rows, to copy-paste
    conversion_results.csv  the same numbers as plain CSV

The input folder must contain xml_files/, csv_files/ and txt_files/,
exactly as the DAG expects.

Column definitions (state these in the paper's caption or methods):

  Files         input files of the expected extension in the folder
  Records       XML: one record per file (one SPL document).
                CSV/TXT: data rows read by pandas (after skiprows).
  Out of scope  records the pipeline skips because they lack the
                deduplication key: XML files whose root is not an SPL
                <document>; CSV/TXT rows with no 'Proper Name' /
                'Ingredient' value (e.g. every row of Orange Book
                patent.txt and exclusivity.txt, which have no
                Ingredient column).
  Duplicates    records skipped because their key was already converted
                earlier in the same run (same rule as jsonifyer, which
                compares keys exactly as strings).
  Malformed     XML that fails to parse; CSV/TXT files that cannot be
                read (all their lines are counted); blank rows.
  Eligible      Records - Out of scope - Duplicates - Malformed
  Converted     records the pipeline would write as JSON
  Success (%)   Converted / Eligible * 100

The counts assume a clean run: all three state files empty at the start
(the DAG empties the TXT one itself, but not the XML and CSV ones).
"""

import argparse
import configparser
import contextlib
import csv
import io
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
from jsonifyer.converter.python_converter import parse_xml_to_json

# ----- the same settings as the DAG ---------------------------------------
XML_FIELDS = {
    'id': './/id/@root',
    'code.code': './/code/@code',
    'code.codeSystem': './/code/@codeSystem',
    'code.displayName': './/code/@displayName',
    'organization': './/author/assignedEntity/representedOrganization/name',
    'name': './/component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct/name',
    'effectiveTime': './/effectiveTime/@value',
    'ingredients.name': './/component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct/ingredient/ingredientSubstance/name',
    'ingredients.code': './/component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct/ingredient/ingredientSubstance/code/@code',
    'ingredients.class_code': './/component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct/ingredient/@classCode',
}
XML_SECTIONS = {
    'indications': '34067-9',
    'contraindications': '34070-3',
    'warningsAndPrecautions': '43685-7',
    'adverseReactions': '34084-4',
}
_ING = './/component/structuredBody/component/section/subject/manufacturedProduct/manufacturedProduct/ingredient'
XML_PAIRS = {
    'ingredients.name': [_ING, 'ingredientSubstance/name'],
    'ingredients.code': [_ING, 'ingredientSubstance/code/@code'],
    'ingredients.class_code': [_ING, '@classCode'],
}
XML_NS = {'': 'urn:hl7-org:v3'}
XML_KEY = 'name'
CSV_KEY, CSV_SKIPROWS = 'Proper Name', 3
TXT_KEY, TXT_DELIM = 'Ingredient', '~'

COLUMNS = ['Files', 'Records', 'Out of scope', 'Duplicates',
           'Malformed', 'Eligible', 'Converted']


def empty_counts():
    return {**{c: 0 for c in COLUMNS}, 'no_key_written': 0, 'notes': []}


def finish(c):
    c['Eligible'] = c['Records'] - c['Out of scope'] - c['Duplicates'] - c['Malformed']
    return c


def xml_key(result):
    """Same normalisation of the key as jsonifyer.api.convert_xml."""
    v = result.get(XML_KEY)
    if isinstance(v, list) and v and isinstance(v[0], dict):
        v = v[0].get('name', '')
    elif isinstance(v, dict) and 'name' in v:
        v = v['name']
    return v


def count_xml(folder):
    c = empty_counts()
    seen = set()
    if not folder.exists():
        c['notes'].append(f'{folder} not found')
        return finish(c)
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith('.xml'):
            continue
        c['Files'] += 1
        c['Records'] += 1
        path = folder / name
        try:
            with contextlib.redirect_stdout(io.StringIO()):   # package debug prints
                result = parse_xml_to_json(
                    str(path), None, field_map=XML_FIELDS, namespaces=XML_NS,
                    root_tag='document', extra_fields=XML_SECTIONS, pairs=XML_PAIRS)
        except ET.ParseError:
            c['Malformed'] += 1
            continue
        if not result:          # root is not an SPL <document>
            c['Out of scope'] += 1
            continue
        key = xml_key(result)
        if key is None:
            # jsonifyer writes these without a duplicate check
            c['Converted'] += 1
            c['no_key_written'] += 1
            continue
        if key in seen:
            c['Duplicates'] += 1
            continue
        seen.add(str(key))
        c['Converted'] += 1
    if c['no_key_written']:
        c['notes'].append(f"{c['no_key_written']} XML files had no product name "
                          "and were converted without a duplicate check")
    return finish(c)


def read_table(path, delimiter, skiprows, latin1_fallback):
    raw = path.read_bytes()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        if not latin1_fallback:
            raise
        text = raw.decode('latin-1')   # what the DAG does for CSV files
    return pd.read_csv(io.StringIO(text), delimiter=delimiter, skiprows=skiprows)


def count_table(folder, ext, key, delimiter, skiprows, latin1_fallback):
    c = empty_counts()
    seen = set()                # shared across files, like the state file
    if not folder.exists():
        c['notes'].append(f'{folder} not found')
        return finish(c)
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(ext):
            continue
        c['Files'] += 1
        path = folder / name
        try:
            df = read_table(path, delimiter, skiprows, latin1_fallback)
        except Exception as e:
            lines = max(sum(1 for _ in open(path, 'rb')) - skiprows - 1, 0)
            c['Records'] += lines
            c['Malformed'] += lines
            c['notes'].append(f'{name}: unreadable ({type(e).__name__}); '
                              f'the DAG would stop here')
            continue
        n = len(df)
        blank = int(df.isna().all(axis=1).sum())
        c['Records'] += n
        c['Malformed'] += blank
        rows = df.dropna(how='all')
        rows = rows.where(pd.notna(rows), None)
        if key not in rows.columns:
            c['Out of scope'] += len(rows)
            c['notes'].append(f"{name}: no '{key}' column, all {len(rows)} rows skipped")
            continue
        empty_keys = 0
        for v in rows[key]:
            if v is None:
                c['Out of scope'] += 1
                continue
            if isinstance(v, float) and v != v:   # NaN: jsonifyer keys it as 'nan'
                empty_keys += 1
            if str(v) in seen:
                c['Duplicates'] += 1
            else:
                seen.add(str(v))
                c['Converted'] += 1
        if empty_keys:
            c['notes'].append(f"{name}: {empty_keys} rows with an empty '{key}' are keyed "
                              "as 'nan' by jsonifyer, so one of them is converted")
    return finish(c)


def pct(conv, elig):
    return f'{100 * conv / elig:.1f}' if elig else '--'


def fmt(n):
    return f'{n:,}'


def write_stats(input_folder, out_dir='.', name='conversion_results'):
    """Count the table values for input_folder and save <name>.txt and <name>.csv
    in out_dir. Returns the two paths. Safe to call from an Airflow task."""
    base = Path(input_folder)
    rows = [
        ('DailyMed', 'XML', count_xml(base / 'xml_files')),
        ('Purple Book', 'CSV', count_table(base / 'csv_files', '.csv', CSV_KEY,
                                            ',', CSV_SKIPROWS, True)),
        ('Orange Book', 'TXT', count_table(base / 'txt_files', '.txt', TXT_KEY,
                                            TXT_DELIM, 0, False)),
    ]
    for src, _, c in rows:
        assert c['Converted'] <= c['Eligible'] + c['no_key_written'], src

    total = {col: sum(r[2][col] for r in rows) for col in COLUMNS}
    table = [(src, f, c) for src, f, c in rows] + [('Total', '', total)]
    notes = [(src, n) for src, _, c in rows for n in c['notes']]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / f'{name}.txt'
    csv_path = out_dir / f'{name}.csv'

    # LaTeX rows, ready to paste between \midrule lines of tab:conversion_results
    lines = [f'% Conversion results, input: {base}']
    for src, f, c in table:
        if src == 'Total':
            lines.append(r'\midrule')
        cells = [fmt(c[col]) for col in COLUMNS] + [pct(c['Converted'], c['Eligible'])]
        lines.append(f'{src} & {f} & ' + ' & '.join(cells) + r' \\')
    if notes:
        lines.append('% Notes:')
        lines += [f'% {src}: {n}' for src, n in notes]
    txt_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    # The same table as plain numbers, for checking or for csvsimple/pgfplotstable
    with open(csv_path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['Source', 'Format'] + COLUMNS + ['Success (%)'])
        for src, f, c in table:
            w.writerow([src, f] + [c[col] for col in COLUMNS]
                       + [pct(c['Converted'], c['Eligible'])])

    print('\n'.join(lines))
    print(f'\nSaved {txt_path} and {csv_path}')
    return txt_path, csv_path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input_folder', nargs='?',
                    help='folder with xml_files/, csv_files/, txt_files/')
    ap.add_argument('--ini', help='read base_input_folder from this jsonify.ini')
    ap.add_argument('--out-dir', default='.',
                    help='where to save the results (default: current folder)')
    ap.add_argument('--name', default='conversion_results',
                    help='base name of the .txt and .csv files (default: conversion_results)')
    args = ap.parse_args()

    if args.ini:
        cfg = configparser.ConfigParser()
        cfg.read(args.ini)
        base = cfg['folders']['base_input_folder']
    elif args.input_folder:
        base = args.input_folder
    else:
        ap.error('give an input folder or --ini')

    write_stats(base, args.out_dir, args.name)
    return 0


if __name__ == '__main__':
    sys.exit(main())