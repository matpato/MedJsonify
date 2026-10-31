###############################################################################
#                                                                             #  
# @file: knowledge_graph.py                                                   #  
# @description: Neo4j knowledge graph creation for pharmaceutical data        #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This module handles the creation of a pharmaceutical knowledge graph in     #
# Neo4j. It processes JSON data containing drug and disease information,      #
# normalizes identifiers, and creates nodes and relationships in the graph    #
# database. The resulting knowledge graph represents drugs, diseases, and     #
# their relationships such as indications and contraindications.              #
#                                                                             #  
###############################################################################

import json
import os
import re
from neo4j import GraphDatabase
from datetime import datetime

# Generic ontology terms that are not real diseases. Linking drugs to them creates
# hub nodes that connect unrelated drugs and distort downstream analyses.
# Add or remove IDs here; the filter applies to nodes and to the drug-disease relations.
EXCLUDED_DISEASE_IDS = {
    "DOID:4",             # disease (root of the Disease Ontology)
    "DOID:225",           # syndrome
    "Orphanet_377788",    # generic Orphanet class (name "Unknown")
    "Orphanet_557493",    # generic Orphanet class (name "Unknown")
    # Ontology entries whose name is a common word or a non-disease concept
    "Orphanet_168345",    # matched "insulin"
    "Orphanet_467238",    # matched "proton pump"
    "HP:0032940",         # matched "dissociation" (chemical sense in labels)
}

# Short mentions: after lower-casing, a single word of up to 4 letters is
# ambiguous (an English word such as "not", "type", "men", "face", or an
# acronym such as "cll", "mmf", "csf" that NER cannot resolve), so the link is
# dropped. Real disease words of that length are kept.
SHORT_MENTION_MAX = 4
SHORT_DISEASE_WORDS = {"pain", "rash", "coma", "yaws", "tics", "gout", "acne", "flu"}


def is_excluded_disease(item):
    """
    True when a disease link is removed by the ontology cleanup (S3 -> S4):
    a generic or non-disease term (EXCLUDED_DISEASE_IDS), or an ambiguous
    short mention (SHORT_MENTION_MAX, SHORT_DISEASE_WORDS).
    """
    if item.get("id") in EXCLUDED_DISEASE_IDS:
        return True
    mention = (item.get("name") or "").strip().lower()
    return (bool(mention) and len(mention) <= SHORT_MENTION_MAX
            and re.fullmatch(r"[a-z0-9]+", mention) is not None
            and mention not in SHORT_DISEASE_WORDS)

# Relationship types, as named in the paper
REL_INDICATION = "has_indication"
REL_CONTRAINDICATION = "has_contraindication"
REL_ADMINISTRATION = "has_administration"
REL_APPROVED_YEAR = "has_approved_year"

# One node per disease: ORDO/HPO ids mapped to the equivalent DO id
try:
    from database.disease_mapping import canonical_disease
except ImportError:
    from disease_mapping import canonical_disease


class Neo4jHandler:
    """
    Handles interactions with the Neo4j graph database.

    Creates a pharmaceutical knowledge graph: nodes for drugs, diseases,
    administration routes and approval years, and the relationships
    has_indication, has_contraindication, has_administration and
    has_approved_year between them.
    """

    def __init__(self, uri, user, password):
        """
        Open the connection and make sure the uniqueness constraints exist
        (they also create the indexes MERGE needs to stay fast).
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.create_constraints()

    def close(self):
        """Close the Neo4j database connection."""
        self.driver.close()

    def create_constraints(self):
        """Uniqueness constraints (Neo4j 5 syntax; Neo4j 4.x syntax as fallback)."""
        constraints = (("drug_id", "Drug", "id"), ("disease_id", "Disease", "id"),
                       ("route_name", "AdminRoute", "name"), ("year_value", "ApprovalYear", "year"))
        with self.driver.session() as session:
            for name, label, prop in constraints:
                try:
                    session.run(f"CREATE CONSTRAINT {name} IF NOT EXISTS "
                                f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")
                except Exception:
                    session.run(f"CREATE CONSTRAINT IF NOT EXISTS ON (n:{label}) "
                                f"ASSERT n.{prop} IS UNIQUE")

    def create_drug(self, drug):
        """Create a Drug node (the name is the one of its first record)."""
        query = """
        MERGE (d:Drug {id: $id})
        ON CREATE SET d.name = $name, d.organization = $organization,
                      d.effectiveTime = $effectiveTime
        """
        with self.driver.session() as session:
            session.run(query, id=drug["id"], name=drug.get("name"),
                        organization=drug.get("organization"),
                        effectiveTime=drug.get("effectiveTime"))

    def create_disease(self, disease):
        """Create a Disease node (the name is the one of its first mention)."""
        query = """
        MERGE (d:Disease {id: $id})
        ON CREATE SET d.name = $name
        """
        with self.driver.session() as session:
            session.run(query, id=disease["id"], name=disease.get("name"))

    def create_admin_route(self, route, drug_id):
        """Link a drug to its administration route(s); one node per route (see normalize_routes)."""
        with self.driver.session() as session:
            for r in normalize_routes(route):
                session.run(f"""
                MERGE (r:AdminRoute {{name: $route}})
                WITH r
                MATCH (d:Drug {{id: $drug_id}})
                MERGE (d)-[:{REL_ADMINISTRATION}]->(r)
                """, route=r, drug_id=drug_id)

    def create_approval_year(self, year, drug_id):
        """Link a drug to its approval year (stored as an integer)."""
        try:
            year = int(year) if year else None
        except (TypeError, ValueError):
            year = None
        if not year:
            return
        with self.driver.session() as session:
            session.run(f"""
            MERGE (y:ApprovalYear {{year: $year}})
            WITH y
            MATCH (d:Drug {{id: $drug_id}})
            MERGE (d)-[:{REL_APPROVED_YEAR}]->(y)
            """, year=year, drug_id=drug_id)

    def create_relationships(self, drug_id, indications, contraindications):
        """has_indication / has_contraindication between a drug and diseases."""
        with self.driver.session() as session:
            for rel, items in ((REL_INDICATION, indications), (REL_CONTRAINDICATION, contraindications)):
                for item in items:
                    session.run(f"""
                    MATCH (d:Drug {{id: $drug_id}}), (dis:Disease {{id: $dis_id}})
                    MERGE (d)-[:{rel}]->(dis)
                    """, drug_id=drug_id, dis_id=item["id"])

    def insert_data(self, drug, diseases, indications, contraindications):
        """
        Insert all data for a drug: the drug, its diseases (without the links
        removed by the ontology cleanup, is_excluded_disease), route(s),
        approval year and relations.
        """
        indications = [i for i in indications if not is_excluded_disease(i)]
        contraindications = [c for c in contraindications if not is_excluded_disease(c)]
        linked = {x["id"] for x in indications + contraindications}
        diseases = [d for d in diseases if d["id"] in linked]

        self.create_drug(drug)
        for disease in diseases:
            self.create_disease(disease)
        self.create_admin_route(drug.get("admin_route"), drug["id"])
        self.create_approval_year(drug.get("approval_year"), drug["id"])
        self.create_relationships(drug["id"], indications, contraindications)

# -------------------------------------------------------------------------------------------- #
# UTILITY FUNCTIONS FOR PROCESSING DATA
# -------------------------------------------------------------------------------------------- #

def load_json(file_path):
    """Load JSON data from a file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_id(url):
    """
    Extract a clean identifier from a URL or ID string, normalized to CURIE format
    (e.g. .../CHEBI_17234 -> CHEBI:17234, .../DOID_2841 -> DOID:2841;
    Orphanet ids stay as Orphanet_nnn).
    """
    if not url or not isinstance(url, str):
        return None
    last_segment = url.rstrip('/').split('/')[-1]
    if '_' in last_segment:
        prefix, _, local_id = last_segment.partition('_')
        if prefix.isupper() and local_id.isdigit():
            return f"{prefix}:{local_id}"
    return last_segment

def extract_year(approval_date):
    """Year (as a string) from 'Mar 15, 2022', 'March 15, 2022', '20220315' or '2022'."""
    if not approval_date:
        return None
    if isinstance(approval_date, int):
        return str(approval_date)[:4]
    if isinstance(approval_date, str):
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                return str(datetime.strptime(approval_date, fmt).year)
            except ValueError:
                pass
        if approval_date.isdigit() and len(approval_date) in (4, 8):
            return approval_date[:4]
    return None

# Values that are not administration routes (Orange Book): no route node
NOT_ROUTES = {'n/a', 'na', 'none', 'unknown', 'not applicable', 'for rx compounding'}
# Synonyms: DailyMed (SPL) names -> Orange Book names, one node per route
ROUTE_SYNONYMS = {
    'auricular (otic)': 'otic',
    'respiratory (inhalation)': 'inhalation',
}
# Orange Book pack variants of oral contraceptives: ORAL-20, ORAL-21, ORAL-28
_ORAL_PACK = re.compile(r"^oral-\d+$")

def normalize_routes(route):
    """
    Administration route(s) as a list of lower-case names, one node per route:
    'INTRAVENOUS' and 'Intravenous' are the same route, 'ORAL-28' is oral and
    'AURICULAR (OTIC)' is otic; values that are not routes ('N/A', 'FOR RX
    COMPOUNDING') are dropped. Accepts a string with several routes separated
    by ',' or ';', or a list (labels with several products).
    """
    if not route:
        return []
    values = route if isinstance(route, list) else [route]
    routes = []
    for value in values:
        for r in re.split(r"[,;]", str(value)):
            r = re.sub(r"\s+", " ", r).strip().lower()
            if _ORAL_PACK.match(r):
                r = 'oral'
            r = ROUTE_SYNONYMS.get(r, r)
            if r and r not in NOT_ROUTES and r not in routes:
                routes.append(r)
    return routes

def route_from_df_route(df_route):
    """Orange Book 'DF;Route' ('TABLET;ORAL', 'INJECTION;INTRAMUSCULAR, INTRAVENOUS') -> route part."""
    if not df_route or ';' not in str(df_route):
        return None
    return str(df_route).split(';', 1)[1].strip() or None

def as_text(value):
    """A name field as text (labels with several products give a list: first name)."""
    if isinstance(value, list):
        value = next((v for v in value if isinstance(v, str) and v.strip()), '')
    return value.strip() if isinstance(value, str) else None

# Ontology entity lists in the NER output, with the field(s) holding the ID
DISEASE_SOURCES = (
    ("doid_entities",     ("doid_id",)),
    ("orphanet_entities", ("orphanet_id", "id")),
    ("hpo_entities",      ("hpo_id", "id")),
)

def _clean_disease_name(text):
    """Remove a trailing ' (DOID:...)', ' (HP:...)' or ' (ORPHA:...)' from a mention."""
    return re.sub(r"\s*\((DOID|HP|ORPHA)[:_][^)]*\)\s*$", "", text or "Unknown")

def _disease_entities(section):
    """
    Yield (disease_id, name) for every DOID, ORDO and HPO entity in a section,
    with ORDO/HPO ids mapped to the equivalent DO id when there is one, and
    each disease once.
    """
    if not isinstance(section, dict):
        return
    # One name per disease: the longest mention in the section, so that
    # "urinary tract infections" is kept over its abbreviation "uti" (the
    # cleanup drops links whose only mentions are short and ambiguous)
    best = {}
    for list_key, id_fields in DISEASE_SOURCES:
        for entity in section.get(list_key, []) or []:
            if not isinstance(entity, dict):
                continue
            raw_id = next((entity.get(f) for f in id_fields if entity.get(f)), None)
            name = _clean_disease_name(entity.get("text") or entity.get("disease"))
            disease_id = canonical_disease(clean_id(raw_id), name)
            if disease_id and (disease_id not in best or len(name) > len(best[disease_id])):
                best[disease_id] = name
    for disease_id, name in best.items():
        yield disease_id, name

# Approval years from the Orange Book / Purple Book (see approval_years.py)
try:
    from database.approval_years import approval_year, parse_year
except ImportError:
    from approval_years import approval_year, parse_year

# Active ingredients that are never the therapeutic component of a product
# (e.g. the alcohol in a kit's prep pad). Keep this list short and report it in the paper.
NON_THERAPEUTIC_ACTIVES = {"WATER", "ISOPROPYL ALCOHOL"}


def process_xml_file(file_path, neo4j_handler, active_only=True):
    """
    Process a JSON file (NER output) and load its data into Neo4j.

    Drug IDs: DrugBank first, ChEBI as fallback, in every source, so that the
    same drug gets the same node whichever source it comes from.

    Diseases: DOID, ORDO and HPO entities; ORDO/HPO ids are mapped to the
    equivalent DO id when there is one (disease_mapping.py).

    Approval year:
      - DailyMed: year of the FDA application (approval_id) in the Orange Book
        or Purple Book; the product's first marketing date as a fallback.
        The label's effectiveTime is a label-version date and is not used.
      - Orange Book / Purple Book: their own approval date.

    Routes: DailyMed admin_route, Purple Book 'Route of Administration',
    Orange Book 'DF;Route' (route part); one node per route (normalize_routes).

    Args:
        file_path (str): Path to the JSON file
        neo4j_handler: Neo4jHandler, or any object with insert_data()
        active_only (bool): DailyMed: only active ingredients (the graph);
            False counts every identified ingredient (dataflow table, S2)
    """
    try:
        data = load_json(file_path)

        if "ingredients" in data:
            # XML-derived file (DailyMed): use only ingredients marked active by the SPL
            ingredients = [
                ingredient for ingredient in data.get("ingredients", [])
                if not active_only or (
                    (ingredient.get("class_code") or "").upper().startswith("ACT")
                    and (as_text(ingredient.get("name")) or "").upper() not in NON_THERAPEUTIC_ACTIVES)
            ]
            if not ingredients:
                return

            # Diseases are the same for every active ingredient of the product
            diseases, indications, contraindications = [], [], []
            for disease_id, name in _disease_entities(data.get("indications")):
                diseases.append({"id": disease_id, "name": name})
                indications.append({"id": disease_id, "name": name})
            for disease_id, name in _disease_entities(data.get("contraindications")):
                diseases.append({"id": disease_id, "name": name})
                contraindications.append({"id": disease_id, "name": name})

            # Approval year of the product's FDA application (same for all its ingredients)
            year, year_source = approval_year(data.get("approval_id"),
                                              data.get("marketing_start"))

            seen = set()
            for ingredient in ingredients:
                chebi_id = clean_id(ingredient.get("chebi_id"))
                drugbank_id = clean_id(ingredient.get("drugbank_id"))

                # Use DrugBank ID as primary identifier, fallback to CHEBI ID
                drug_id = drugbank_id or chebi_id
                if not drug_id or drug_id in seen:
                    continue
                seen.add(drug_id)

                drug = {
                    "id": drug_id,
                    "name": as_text(ingredient.get("name")),
                    "organization": as_text(data.get("organization")),
                    "effectiveTime": as_text(data.get("effectiveTime")),
                    "admin_route": data.get("admin_route"),
                    "approval_year": year,
                    "approval_year_source": year_source,
                    "application": data.get("approval_id"),
                    "chebi_id": chebi_id,
                    "drugbank_id": drugbank_id,
                }

                print(f"Drug: {drug_id} (DrugBank: {drugbank_id}, CHEBI: {chebi_id})")
                print(f"Admin Route: {normalize_routes(drug.get('admin_route'))}, "
                      f"Approval Year: {year} ({year_source or 'not found'})")
                print(f"Found {len(diseases)} diseases, {len(indications)} indications, "
                      f"{len(contraindications)} contraindications")

                neo4j_handler.insert_data(drug, diseases, indications, contraindications)

        else:
            # Regular JSON file (Orange Book / Purple Book)
            for drug_entry in data.get("drug", []):
                chebi_id = clean_id(drug_entry.get("chebi_id"))
                drugbank_id = clean_id(drug_entry.get("drugbank_id"))

                # Use DrugBank ID as primary identifier, fallback to CHEBI ID
                # (same order as for DailyMed, so the same drug is one node)
                drug_id = drugbank_id or chebi_id
                if not drug_id:
                    continue

                # The source's own approval date (not a label date)
                approval_date = (
                    data.get("Approval_Date") or
                    data.get("Approval Date") or
                    drug_entry.get("approval_date")
                )
                # parse_year also reads the Purple Book's two-digit years ("3-Nov-03")
                approval_year_value = parse_year(approval_date)
                if approval_date and "prior to" in str(approval_date).lower():
                    approval_year_value = None      # "Approved Prior to Jan 1, 1982"
                admin_route = (drug_entry.get("admin_route")
                               or data.get("Route of Administration")          # Purple Book
                               or route_from_df_route(data.get("DF;Route")))   # Orange Book

                drug = {
                    "id": drug_id,
                    "name": as_text(drug_entry.get("name")),
                    "organization": as_text(data.get("organization") or data.get("Applicant")),
                    "effectiveTime": as_text(data.get("effectiveTime")),
                    "admin_route": admin_route,
                    "approval_year": approval_year_value,
                    "approval_year_source": "orange_book" if "Approval_Date" in data else
                                            ("purple_book" if "Approval Date" in data else None),
                    "chebi_id": chebi_id,
                    "drugbank_id": drugbank_id,
                }

                print(f"Drug: {drug_id} (DrugBank: {drugbank_id}, CHEBI: {chebi_id})")
                print(f"Admin Route: {normalize_routes(admin_route)}, Approval Year: {approval_year_value}")

                # Orange/Purple Book records have no indication text: no diseases
                neo4j_handler.insert_data(drug, [], [], [])

    except Exception as e:
        print(f"Error processing file '{file_path}': {e}")