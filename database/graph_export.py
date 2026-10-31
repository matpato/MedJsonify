###############################################################################
#                                                                             #
# @file: graph_export.py                                                      #
# @description: Export Neo4j knowledge graph relationships to CSV files       #
# @date: October 2026                                                         #
# @version: 1.0                                                               #
#                                                                             #
# Exports two CSV files from the Neo4j knowledge graph:                       #
#   - indicated.csv        : Drug -[has_indication]-> Disease                 #
#   - contraindicated.csv  : Drug -[has_contraindication]-> Disease           #
#                                                                             #
###############################################################################

import csv
import logging
import os
from neo4j import GraphDatabase

try:
    from database.knowledge_graph import (EXCLUDED_DISEASE_IDS,      # inside Airflow
                                          REL_INDICATION, REL_CONTRAINDICATION)
except ImportError:
    from knowledge_graph import (EXCLUDED_DISEASE_IDS,               # standalone run
                                 REL_INDICATION, REL_CONTRAINDICATION)


# ---------------------------------------------------------------------------- #
# Queries
# ---------------------------------------------------------------------------- #

QUERY_INDICATED = f"""
MATCH (d:Drug)-[:{REL_INDICATION}]->(dis:Disease)
WHERE NOT dis.id IN $excluded
  // contraindication veto: a drug-disease pair that is also contraindicated is not exported as indicated
  AND NOT (d)-[:{REL_CONTRAINDICATION}]->(dis)
RETURN d.id AS drug_code, dis.id AS disease_code
ORDER BY d.id, dis.id
"""

QUERY_CONTRAINDICATED = f"""
MATCH (d:Drug)-[:{REL_CONTRAINDICATION}]->(dis:Disease)
WHERE NOT dis.id IN $excluded
RETURN d.id AS drug_code, dis.id AS disease_code
ORDER BY d.id, dis.id
"""


# ---------------------------------------------------------------------------- #
# Export function
# ---------------------------------------------------------------------------- #

def export_graph_to_csv(uri: str,
                        user: str,
                        password: str,
                        output_dir: str) -> dict:
    """
    Export drug-disease relationships from Neo4j to CSV files.

    Args:
        uri:        Neo4j connection URI
        user:       Neo4j username
        password:   Neo4j password
        output_dir: Directory where CSVs will be written

    Returns:
        Dictionary with output file paths and row counts, e.g.
        {
            'indicated':       {'path': '...', 'rows': N},
            'contraindicated': {'path': '...', 'rows': N},
        }
    """
    os.makedirs(output_dir, exist_ok=True)

    indicated_path       = os.path.join(output_dir, 'indicated.csv')
    contraindicated_path = os.path.join(output_dir, 'contraindicated.csv')

    driver = GraphDatabase.driver(uri, auth=(user, password))
    results = {}

    try:
        with driver.session() as session:

            # --- indicated.csv ---
            logging.info("Exporting indicated relationships...")
            records = session.run(QUERY_INDICATED, excluded=sorted(EXCLUDED_DISEASE_IDS)).data()
            records = [{'drug:code': r['drug_code'], 'disease:code': r['disease_code']} for r in records]
            _write_csv(indicated_path, fieldnames=['drug:code', 'disease:code'], rows=records)
            results['indicated'] = {'path': indicated_path, 'rows': len(records)}
            logging.info(f"  Wrote {len(records)} rows -> {indicated_path}")


            # --- contraindicated.csv ---
            logging.info("Exporting contraindicated relationships...")
            records = session.run(QUERY_CONTRAINDICATED, excluded=sorted(EXCLUDED_DISEASE_IDS)).data()
            records = [{'drug:code': r['drug_code'], 'disease:code': r['disease_code']} for r in records]
            _write_csv(contraindicated_path, fieldnames=['drug:code', 'disease:code'], rows=records)
            results['contraindicated'] = {'path': contraindicated_path, 'rows': len(records)}
            logging.info(f"  Wrote {len(records)} rows -> {contraindicated_path}")

    finally:
        driver.close()

    return results


# ---------------------------------------------------------------------------- #
# Helper
# ---------------------------------------------------------------------------- #

def _write_csv(path: str, fieldnames: list, rows: list):
    """Write a list of dicts to a CSV file (no header row)."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerows(rows)


# ---------------------------------------------------------------------------- #
# Standalone usage
# ---------------------------------------------------------------------------- #

if __name__ == '__main__':
    import configparser

    logging.basicConfig(level=logging.INFO)

    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(os.path.dirname(__file__), 'neo4j.ini'))

    results = export_graph_to_csv(
        uri=cfg['neo4j']['uri'],
        user=cfg['neo4j']['user'],
        password=cfg['neo4j']['password'],
        output_dir=os.path.join(os.path.dirname(__file__), 'output'),
    )

    print("\nExport complete:")
    for name, info in results.items():
        print(f"  {name}: {info['rows']} rows -> {info['path']}")