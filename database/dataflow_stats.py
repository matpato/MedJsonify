"""
Rows S2-S4 of the dataflow table, computed from the NER output with the
graph-loading code itself (knowledge_graph.process_xml_file), without Neo4j:
a stand-in handler records what would be inserted.

  S2  after NER and entity linking: every identified ingredient, active or not
      (process_xml_file with active_only=False)
  S3  after active-ingredient filtering: the drugs that become graph nodes
  S4  after ontology cleanup: S3 without the links removed by
      knowledge_graph.is_excluded_disease (generic and non-disease terms in
      EXCLUDED_DISEASE_IDS, ambiguous short mentions) -- this is what Neo4j
      contains; compare with the count queries in Neo4j

Columns: D drugs, Dis diseases, R routes, Y approval years (distinct nodes);
Ind, CI, Adm, AY distinct (drug, target) pairs, as MERGE creates them in Neo4j.

    bash standalone/run_medjsonify.sh --shell \
      'python3 /opt/airflow/dags/database/dataflow_stats.py NER/data/entities --out-dir NER/data/stats'
"""

import argparse
import contextlib
import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from database.knowledge_graph import (process_xml_file, normalize_routes,
                                          is_excluded_disease)
except ImportError:
    from knowledge_graph import process_xml_file, normalize_routes, is_excluded_disease

COLUMNS = ['D', 'Dis', 'R', 'Y', 'Ind', 'CI', 'Adm', 'AY']


class CountingHandler:
    """Records what Neo4jHandler.insert_data would create, as MERGE does (distinct)."""

    def __init__(self, cleanup=False):
        self.cleanup = cleanup
        self.c = {k: set() for k in COLUMNS}

    def insert_data(self, drug, diseases, indications, contraindications):
        keep = (lambda x: not is_excluded_disease(x)) if self.cleanup else (lambda x: True)
        d = drug['id']
        self.c['D'].add(d)
        for x in filter(keep, indications):
            self.c['Ind'].add((d, x['id']))
            self.c['Dis'].add(x['id'])
        for x in filter(keep, contraindications):
            self.c['CI'].add((d, x['id']))
            self.c['Dis'].add(x['id'])
        for r in normalize_routes(drug.get('admin_route')):
            self.c['R'].add(r)
            self.c['Adm'].add((d, r))
        try:
            year = int(drug.get('approval_year')) if drug.get('approval_year') else None
        except (TypeError, ValueError):
            year = None
        if year:
            self.c['Y'].add(year)
            self.c['AY'].add((d, year))


def json_files(folder):
    for root, _, files in os.walk(folder):
        for name in sorted(files):
            if name.endswith('.json'):
                yield os.path.join(root, name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('entities_dir', help='NER output folder (NER/data/entities)')
    ap.add_argument('--out-dir', default='.', help='where to save dataflow_s2_s4.txt/.csv')
    args = ap.parse_args()

    s2, s3, s4 = CountingHandler(), CountingHandler(), CountingHandler(cleanup=True)
    files = list(json_files(args.entities_dir))
    with contextlib.redirect_stdout(io.StringIO()):      # process_xml_file prints per drug
        for path in files:
            process_xml_file(path, s2, active_only=False)
            process_xml_file(path, s3)
            process_xml_file(path, s4)

    rows = [('S2', 'After NER and entity linking', s2.c),
            ('S3', 'After active-ingredient filtering', s3.c),
            ('S4', 'After ontology cleanup (full KG)', s4.c)]
    lines = [f"% Dataflow rows S2-S4, from {args.entities_dir} ({len(files)} records)"]
    for stage, desc, c in rows:
        lines.append(f"{stage} & {desc} & " + ' & '.join(f"{len(c[k]):,}" for k in COLUMNS) + r' \\')

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, 'dataflow_s2_s4.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    with open(os.path.join(args.out_dir, 'dataflow_s2_s4.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Stage', 'Description'] + COLUMNS)
        for stage, desc, c in rows:
            w.writerow([stage, desc] + [len(c[k]) for k in COLUMNS])
    print('\n'.join(lines))
    print(f"\nSaved {os.path.join(args.out_dir, 'dataflow_s2_s4.txt')} and .csv")


if __name__ == '__main__':
    main()