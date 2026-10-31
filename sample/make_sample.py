"""
Build the MedJsonify test sample: copy, from the full input folders, the source
records of the drugs discussed in the paper (plus a few others) to a separate
folder. The full input is left untouched (files are copied, not moved).

  XML (DailyMed): labels whose ACTIVE ingredients or title mention one of the
                  drugs, at most --per-drug labels per drug
  TXT (Orange Book products.txt): header + rows whose Ingredient matches,
                  at most --rows-per-drug rows per drug
  CSV (Purple Book): the title lines + header + rows whose Proper Name matches
                  one of the biologics in PURPLE_BOOK_DRUGS

    python3 sample/make_sample.py --input jsonify/input --out sample/input
    python3 sample/make_sample.py --input jsonify/input --out sample/input --per-drug 2 --dry-run

The output has the same layout as jsonify/input (xml_files/, txt_files/,
csv_files/), so it can replace jsonify/input in a copy of the repository.
A list of what was selected is written to <out>/../SAMPLE_CONTENTS.md.
"""

import argparse
import collections
import csv
import io
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

# Drugs of the paper: examples, use cases, hubs (lower case, matched as words)
PAPER_DRUGS = [
    'ciprofloxacin',                                  # shortest paths (S5d)
    'posaconazole',                                   # ego network
    'doxycycline', 'minocycline',                     # UC2
    'methylprednisolone', 'hydrocortisone',           # hubs (UC3)
    'prednisone', 'prednisolone',
    'diclofenac', 'ibuprofen', 'indomethacin', 'meloxicam',   # UC1 (NSAIDs)
    'nabumetone', 'naproxen', 'oxaprozin', 'misoprostol',
    'sodium bicarbonate',                             # combination product
    'lidocaine', 'dexamethasone',                     # several routes
]
# Purple Book biologics (licence dates before 1950, a biosimilar family)
PURPLE_BOOK_DRUGS = ['antivenin', 'albumin', 'immune globulin', 'adalimumab']

NS = '{urn:hl7-org:v3}'


def word_pattern(term):
    return re.compile(r'(?<![a-z])' + re.escape(term) + r'(?![a-z])')


def match_terms(text, terms):
    text = (text or '').lower()
    return [t for t in terms if word_pattern(t).search(text)]


# --------------------------------------------------------------------- XML ---

def label_terms(path):
    """Drug terms found in the label's title or ACTIVE ingredient names."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    title = ''.join(root.find(f'{NS}title').itertext()) if root.find(f'{NS}title') is not None else ''
    actives = []
    for ing in root.iter(f'{NS}ingredient'):
        if (ing.get('classCode') or '').upper().startswith('ACT'):
            name = ing.find(f'{NS}ingredientSubstance/{NS}name')
            if name is not None and name.text:
                actives.append(name.text)
    return match_terms(' '.join(actives), PAPER_DRUGS) or match_terms(title, PAPER_DRUGS)


def has_inactive_lactose(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return False
    for ing in root.iter(f'{NS}ingredient'):
        name = ing.find(f'{NS}ingredientSubstance/{NS}name')
        if (ing.get('classCode') or '').upper() == 'IACT' and name is not None \
                and 'lactose' in (name.text or '').lower():
            return True
    return False


def select_xml(xml_dir, per_drug):
    chosen, per = [], collections.Counter()
    lactose_example = None
    for name in sorted(os.listdir(xml_dir)):
        if not name.lower().endswith('.xml'):
            continue
        path = os.path.join(xml_dir, name)
        terms = label_terms(path)
        new = [t for t in terms if per[t] < per_drug]
        if new:
            chosen.append((name, ', '.join(terms)))
            for t in terms:
                per[t] += 1
        elif lactose_example is None and not terms and has_inactive_lactose(path):
            lactose_example = name
    if lactose_example:
        chosen.append((lactose_example, 'lactose as inactive ingredient (excipient filter)'))
    return chosen, per


# --------------------------------------------------------------------- TXT ---

def select_txt(path, rows_per_drug):
    """Orange Book products.txt (tilde-delimited, header 'Ingredient~...')."""
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()
    if not lines:
        return [], collections.Counter()
    header, keep, per = lines[0], [lines[0]], collections.Counter()
    cols = header.split('~')
    idx = cols.index('Ingredient') if 'Ingredient' in cols else 0
    for line in lines[1:]:
        fields = line.split('~')
        if len(fields) <= idx:
            continue
        for t in match_terms(fields[idx], PAPER_DRUGS):
            if per[t] < rows_per_drug:
                keep.append(line)
                for t2 in match_terms(fields[idx], PAPER_DRUGS):
                    per[t2] += 1
                break
    return keep, per


# --------------------------------------------------------------------- CSV ---

def select_csv(path, rows_per_drug):
    """Purple Book data file: title lines + last 'N/R/U,' header + matching rows."""
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        lines = f.read().splitlines()
    headers = [i for i, l in enumerate(lines) if l.startswith('N/R/U,')]
    if not headers:
        return [], collections.Counter()
    h = headers[-1]
    keep, per = lines[:min(3, h)] + [lines[h]], collections.Counter()
    while len(keep) < 4:
        keep.insert(0, '')
    cols = next(csv.reader([lines[h]]))
    idx = cols.index('Proper Name') if 'Proper Name' in cols else 4
    for line in lines[h + 1:]:
        if not line.strip(', '):
            continue
        row = next(csv.reader([line]))
        if len(row) <= idx:
            continue
        for t in match_terms(row[idx], PURPLE_BOOK_DRUGS):
            if per[t] < rows_per_drug:
                keep.append(line)
                per[t] += 1
                break
    return keep, per


# -------------------------------------------------------------------- main ---

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--input', default='jsonify/input')
    ap.add_argument('--out', default='sample/input')
    ap.add_argument('--per-drug', type=int, default=3, help='DailyMed labels per drug (default 3)')
    ap.add_argument('--rows-per-drug', type=int, default=20, help='Orange/Purple Book rows per drug (default 20)')
    ap.add_argument('--dry-run', action='store_true', help='only print what would be copied')
    a = ap.parse_args()

    report = ['# Sample contents', '',
              f'Built by `sample/make_sample.py` from `{a.input}` '
              f'({a.per_drug} labels and {a.rows_per_drug} rows per drug at most).', '']

    # XML
    xml_in = os.path.join(a.input, 'xml_files')
    if os.path.isdir(xml_in):
        chosen, per = select_xml(xml_in, a.per_drug)
        report += ['## DailyMed labels (`xml_files/`)', '', '| File | Drugs |', '|---|---|']
        report += [f'| {n} | {t} |' for n, t in chosen]
        missing = [d for d in PAPER_DRUGS if per[d] == 0]
        if missing:
            report += ['', 'No label found for: ' + ', '.join(missing)]
        report.append('')
        print(f"XML: {len(chosen)} labels")
        if not a.dry_run:
            out = os.path.join(a.out, 'xml_files')
            os.makedirs(out, exist_ok=True)
            for n, _ in chosen:
                shutil.copy2(os.path.join(xml_in, n), out)

    # TXT and CSV
    for sub, fn, label in (('txt_files', select_txt, 'Orange Book'), ('csv_files', select_csv, 'Purple Book')):
        d = os.path.join(a.input, sub)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            ext = '.txt' if sub == 'txt_files' else '.csv'
            if not name.lower().endswith(ext):
                continue
            keep, per = fn(os.path.join(d, name), a.rows_per_drug)
            if not keep:
                continue
            n_rows = len(keep) - (1 if sub == 'txt_files' else 4)
            print(f"{label}: {name}: {n_rows} rows")
            report += [f'## {label} (`{sub}/{name}`)', '', f'{n_rows} rows: ' +
                       ', '.join(f'{t} ({c})' for t, c in sorted(per.items())), '']
            if not a.dry_run:
                os.makedirs(os.path.join(a.out, sub), exist_ok=True)
                with open(os.path.join(a.out, sub, name), 'w', encoding='utf-8', newline='\n') as f:
                    f.write('\n'.join(keep) + '\n')

    report_path = os.path.join(os.path.dirname(os.path.abspath(a.out)), 'SAMPLE_CONTENTS.md')
    if a.dry_run:
        print('\n'.join(report))
    else:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report) + '\n')
        print(f"Sample written to {a.out}; contents listed in {report_path}")


if __name__ == '__main__':
    sys.exit(main())