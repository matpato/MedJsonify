"""
Compare the two XML conversion strategies of jsonifyer on the same SPL files:

  python : jsonifyer's Python converter (parse_xml_to_json), with the field
           map below
  xslt   : the XSLT stylesheet spl_to_json.xsl, applied with lxml exactly as
           jsonifyer's XSLT converter does (no DTD, no network, the FDA
           stylesheet reference removed), output parsed as JSON

Both strategies extract the same fields (set_id, title, admin_route,
approval_id, marketing_start, ingredients, indications, contraindications), so
the only differences are how each one parses and transforms the files.

For every file it records whether each strategy produced a record, the stage
at which it failed (read, parse, transform, json, other) and which fields are
empty. Results:

  <out>/xml_strategy_comparison.txt   summary + LaTeX rows
  <out>/xml_strategy_comparison.csv   one row per file

    bash standalone/run_medjsonify.sh --shell \
      'python3 /opt/airflow/dags/jsonify/xml_strategy_comparison.py \
         /opt/airflow/dags/jsonify/input/xml_files \
         --xslt /opt/airflow/dags/jsonify/spl_to_json.xsl \
         --out /opt/airflow/dags/jsonify/stats'
"""

import argparse
import collections
import contextlib
import csv
import io
import json
import os
import sys
import time

from lxml import etree

try:                                    # jsonifyer installed in the image
    from jsonifyer.converter.python_converter import parse_xml_to_json
except ImportError:                     # local copy (testing)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from jpc_local import parse_xml_to_json

NS = {'': 'urn:hl7-org:v3'}
FIELD_MAP = {
    'set_id': 'setId/@root',
    'title': 'title',
    'admin_route': './/routeCode/@displayName',
    'approval_id': './/approval/id/@extension',
    'marketing_start': './/marketingAct/effectiveTime/low/@value',
}
EXTRA_FIELDS = {'indications': '34067-9', 'contraindications': '34070-3'}
PAIRS = {
    'ingredients.name': ['.//ingredient', 'ingredientSubstance/name'],
    'ingredients.class_code': ['.//ingredient', '@classCode'],
    'ingredients.unii': ['.//ingredient', 'ingredientSubstance/code/@code'],
}
FIELDS = list(FIELD_MAP) + ['ingredients'] + list(EXTRA_FIELDS)
FDA_STYLESHEET = ('<?xml-stylesheet type="text/xsl" '
                  'href="https://www.accessdata.fda.gov/spl/stylesheet/spl.xsl"?>')


def run_python(path):
    """(record or None, failure stage or '', error message)."""
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            rec = parse_xml_to_json(path, None, field_map=FIELD_MAP, namespaces=NS,
                                    extra_fields=EXTRA_FIELDS, pairs=PAIRS)
    except Exception as e:                       # noqa: BLE001 - classify every failure
        stage = 'parse' if type(e).__name__ == 'ParseError' else 'other'
        return None, stage, f"{type(e).__name__}: {e}"
    if not rec:
        return None, 'empty', 'empty record'
    return rec, '', ''


def make_xslt(xslt_path):
    return etree.XSLT(etree.parse(xslt_path))


def run_xslt(path, transform):
    """Same steps as jsonifyer's apply_xslt_to_xml, with the failing stage recorded."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:                       # noqa: BLE001
        return None, 'read', f"{type(e).__name__}: {e}"
    content = content.replace(FDA_STYLESHEET, '')
    try:
        parser = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)
        doc = etree.fromstring(content.encode('utf-8'), parser)
    except Exception as e:                       # noqa: BLE001
        return None, 'parse', f"{type(e).__name__}: {e}"
    try:
        result = transform(doc)
    except Exception as e:                       # noqa: BLE001
        return None, 'transform', f"{type(e).__name__}: {e}"
    try:
        rec = json.loads(str(result))
    except Exception as e:                       # noqa: BLE001
        return None, 'json', f"{type(e).__name__}: {e}"
    if not rec:
        return None, 'empty', 'empty record'
    return rec, '', ''


def empty_fields(rec):
    if rec is None:
        return FIELDS
    return [f for f in FIELDS if rec.get(f) in (None, '', [], {})]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('xml_dir')
    ap.add_argument('--xslt', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spl_to_json.xsl'))
    ap.add_argument('--out', default='.')
    args = ap.parse_args()

    files = sorted(os.path.join(args.xml_dir, n) for n in os.listdir(args.xml_dir)
                   if n.lower().endswith('.xml'))
    if not files:
        sys.exit(f"No .xml files in {args.xml_dir}")
    transform = make_xslt(args.xslt)

    rows = []
    stats = {s: {'ok': 0, 'fail': collections.Counter(), 'empty': collections.Counter(), 'time': 0.0}
             for s in ('python', 'xslt')}
    for i, path in enumerate(files, 1):
        row = {'file': os.path.basename(path)}
        for name, fn in (('python', lambda p: run_python(p)), ('xslt', lambda p: run_xslt(p, transform))):
            t0 = time.time()
            rec, stage, err = fn(path)
            stats[name]['time'] += time.time() - t0
            if rec is None:
                stats[name]['fail'][stage] += 1
            else:
                stats[name]['ok'] += 1
                for f in empty_fields(rec):
                    stats[name]['empty'][f] += 1
            row[f'{name}_ok'] = int(rec is not None)
            row[f'{name}_stage'] = stage
            row[f'{name}_error'] = err[:300]
            row[f'{name}_empty_fields'] = ';'.join(empty_fields(rec)) if rec is not None else ''
        rows.append(row)
        if i % 200 == 0:
            print(f"  {i}/{len(files)} files", flush=True)

    n = len(files)
    both_ok = sum(r['python_ok'] and r['xslt_ok'] for r in rows)
    only_py = sum(r['python_ok'] and not r['xslt_ok'] for r in rows)
    only_xs = sum(r['xslt_ok'] and not r['python_ok'] for r in rows)

    lines = [f"XML conversion strategies on {n} files ({args.xml_dir})", ""]
    for name in ('python', 'xslt'):
        s = stats[name]
        failed = n - s['ok']
        lines.append(f"{name:<7} converted {s['ok']:,} / {n:,}  failed {failed:,} ({100 * failed / n:.1f}%)"
                     f"  time {s['time']:.1f}s")
        for stage, c in s['fail'].most_common():
            lines.append(f"          failed at {stage}: {c:,}")
        for f, c in s['empty'].most_common():
            lines.append(f"          empty '{f}' in {c:,} converted records")
    lines += ["", f"both converted: {both_ok:,}; only Python: {only_py:,}; only XSLT: {only_xs:,}", "",
              "% LaTeX (failed files, share)"]
    for name, label in (('python', 'Python'), ('xslt', 'XSLT')):
        failed = n - stats[name]['ok']
        lines.append(f"{label} & {stats[name]['ok']:,} & {failed:,} & {100 * failed / n:.1f}\\% \\\\")

    os.makedirs(args.out, exist_ok=True)
    txt = os.path.join(args.out, 'xml_strategy_comparison.txt')
    with open(txt, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    with open(os.path.join(args.out, 'xml_strategy_comparison.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print('\n'.join(lines))
    print(f"\nSaved {txt} and xml_strategy_comparison.csv")


if __name__ == '__main__':
    main()