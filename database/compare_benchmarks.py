#!/usr/bin/env python3
"""
compare_benchmarks.py -- compare MedJsonify drug-disease triples with reference resources.

Computes precision, recall and F1 for has_indication and has_contraindication against:
  * PharmacotherapyDB (indications.tsv; physician-curated; DrugBank + DOID)
  * Hetionet v1.0 edges (CtD "treats" and CpD "palliates"; DrugBank + DOID)
  * DrugCentral (CSV exported with the SQL query below; indications + contraindications; UMLS CUI)

Two matching modes:
  strict  : the predicted disease and the reference disease are the same concept
            (same ID, or IDs declared equivalent through ontology xrefs, e.g. DOID <-> UMLS <-> ORDO)
  lenient : also accepts a direct parent or child in the Disease Ontology is_a hierarchy

Only drugs present in BOTH the graph and the reference are evaluated (otherwise recall is
penalised for drugs the graph never contained). For references with a small disease
vocabulary (PharmacotherapyDB, Hetionet), predictions are also restricted to diseases the
reference covers (--restrict-diseases, on by default for these two).

Requirements: Python 3.8+, no third-party packages.

-----------------------------------------------------------------------------------------
INPUT 1 -- your triples (CSV or TSV, header required). Default column names:
    drug_id, relation, disease_id         (required)
    drug_name, disease_name, drugbank_id  (optional; used for matching and for the review file)
  relation values: has_indication / has_contraindication
  drug_id may be a DrugBank ID (DB00001), a ChEBI ID, or anything else; if it is not a DrugBank
  ID, give a drugbank_id column or a drug_name column (names are matched case-insensitively).
  disease_id may be CURIEs (DOID:1040, HP:0001250, Orphanet:558) or URIs
  (http://purl.obolibrary.org/obo/DOID_1040, http://www.orpha.net/ORDO/Orphanet_558).

  Example Cypher export from Neo4j (adjust property names):
    MATCH (d:Drug)-[r:has_indication|has_contraindication]->(x:Disease)
    RETURN d.id AS drug_id, d.name AS drug_name, d.drugbank_id AS drugbank_id,
           type(r) AS relation, x.id AS disease_id, x.name AS disease_name

INPUT 2 -- ontology files in OBO format (used for xref equivalences and the is_a hierarchy):
    --obo doid.obo  [--obo hp.obo] [--obo mondo.obo]
  doid.obo is required. mondo.obo is recommended: it bridges DOID, Orphanet, UMLS and HP.
    https://raw.githubusercontent.com/DiseaseOntology/HumanDiseaseOntology/main/src/ontology/doid.obo
    http://purl.obolibrary.org/obo/hp.obo
    http://purl.obolibrary.org/obo/mondo.obo

INPUT 3 -- DrugCentral export. Query against the DrugCentral PostgreSQL database
  (local dump, or the public read-only instance documented on drugcentral.org) and save as CSV:

    SELECT s.name AS drug_name, i.identifier AS drugbank_id,
           o.relationship_name, o.concept_name, o.umls_cui, o.snomed_conceptid
    FROM omop_relationship o
    JOIN structures s ON s.id = o.struct_id
    LEFT JOIN identifier i ON i.struct_id = s.id AND i.id_type = 'DRUGBANK_ID'
    WHERE o.relationship_name IN ('indication', 'contraindication');

  (Check table/column names against your DrugCentral version.)

-----------------------------------------------------------------------------------------
USAGE
  python3 compare_benchmarks.py evaluate \
      --triples medjsonify_triples.tsv \
      --obo doid.obo --obo mondo.obo \
      --pharmacotherapydb indications.tsv \
      --hetionet hetionet-v1.0-edges.sif.gz --hetionet-nodes hetionet-v1.0-nodes.tsv \
      --drugcentral drugcentral_export.csv \
      --out results/

  With the graph export (graph_export.py) and Hetionet as pairs:
  python3 compare_benchmarks.py evaluate \
      --indicated database/output/indicated.csv \
      --contraindicated database/output/contraindicated.csv \
      --obo doid.obo --hetionet-pairs hetionet_indicated.csv --out results/

  Outputs in results/:
    metrics.csv          one row per reference x relation x matching mode
    disagreements.csv    random sample of false positives and false negatives for manual
                         review, with empty columns annotator_A / annotator_B / category
    unmapped.csv         reference diseases that could not be mapped to any ontology ID

  After two people fill annotator_A and annotator_B in disagreements.csv:
  python3 compare_benchmarks.py kappa --file results/disagreements.csv
"""

import argparse
import csv
import gzip
import io
import os
import random
import re
import sys
from collections import defaultdict

IND, CI = "has_indication", "has_contraindication"

# ---------------------------------------------------------------------------------------
# Identifier normalisation
# ---------------------------------------------------------------------------------------

_PREFIX_ALIASES = {
    "DOID": "DOID",
    "HP": "HP",
    "MONDO": "MONDO",
    "UMLS": "UMLS", "UMLS_CUI": "UMLS",
    "ORPHANET": "ORPHA", "ORPHA": "ORPHA", "ORDO": "ORPHA",
    "MESH": "MESH", "MSH": "MESH",
    "SCTID": "SNOMED", "SNOMEDCT": "SNOMED", "SNOMEDCT_US": "SNOMED", "SNOMED": "SNOMED",
    "OMIM": "OMIM", "MIM": "OMIM",
    "NCIT": "NCIT", "NCI": "NCIT",
    "ICD10CM": "ICD10CM", "ICD9CM": "ICD9CM",
}


def norm_id(raw):
    """Return a canonical 'PREFIX:LOCAL' string, or None if the input is unusable."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # URIs: .../DOID_1040, .../HP_0001250, .../Orphanet_558, .../MONDO_0005148
    m = re.search(r"/([A-Za-z]+)_([A-Za-z0-9]+)$", s)
    if m and ("://" in s):
        prefix, local = m.group(1), m.group(2)
    elif ":" in s:
        prefix, local = s.split(":", 1)
        # SNOMEDCT_US_2023_03_01:12345 -> SNOMEDCT_US
        prefix = re.sub(r"_\d{4}(_\d{2}){0,2}$", "", prefix)
    elif re.fullmatch(r"C\d{7}", s):
        prefix, local = "UMLS", s
    else:
        return None
    p = _PREFIX_ALIASES.get(prefix.upper())
    if p is None:
        return None
    local = local.strip()
    if p == "UMLS":
        local = local.upper()
    return f"{p}:{local}"


def norm_name(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def norm_drugbank(s):
    s = (s or "").strip()
    if s.lower().startswith("compound::"):
        s = s.split("::", 1)[1]
    m = re.fullmatch(r"(?i)(?:drugbank:)?(DB\d{5})", s)
    return m.group(1).upper() if m else None

# ---------------------------------------------------------------------------------------
# Ontologies: union-find over IDs + xrefs, and DO is_a neighbours
# ---------------------------------------------------------------------------------------


# Only these identifier types are treated as equivalences when read from xrefs.
# ICD, MeSH, OMIM, NCIt, SNOMED, EFO... are often shared by several distinct diseases and
# would merge unrelated concepts.
EQUIV_PREFIXES = {"UMLS", "ORPHA", "MONDO", "DOID", "HP"}


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


class Ontologies:
    def __init__(self):
        self.uf = UnionFind()
        self.neighbours = defaultdict(set)  # DO is_a parents and children
        self.known = set()

    def load_obo(self, path):
        cur, obsolete, xrefs, parents = None, False, [], []

        def flush():
            if cur and not obsolete:
                self.known.add(cur)
                self.uf.find(cur)
                for x in xrefs:
                    self.known.add(x)
                    self.uf.union(cur, x)
                for p in parents:
                    self.neighbours[cur].add(p)
                    self.neighbours[p].add(cur)

        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line.startswith("["):
                    flush()
                    cur, obsolete, xrefs, parents = None, False, [], []
                    if line != "[Term]":
                        cur = None
                    continue
                if line.startswith("id: "):
                    cur = norm_id(line[4:].split()[0])
                elif line.startswith("is_obsolete: true"):
                    obsolete = True
                elif line.startswith("xref: "):
                    x = norm_id(line[6:].split()[0])
                    # MONDO marks true equivalences with source="MONDO:equivalentTo"
                    qualified = "{" in line and "source=" in line
                    if qualified and "MONDO:equivalentTo" not in line:
                        continue
                    if x and x.split(":", 1)[0] in EQUIV_PREFIXES:
                        xrefs.append(x)
                elif line.startswith("is_a: ") and cur and cur.startswith("DOID:"):
                    p = norm_id(line[6:].split()[0])
                    if p:
                        parents.append(p)
            flush()

    def clusters(self, ident, lenient=False):
        """Set of equivalence-class roots for one ID (plus DO neighbours if lenient)."""
        if ident is None:
            return set()
        out = {self.uf.find(ident)}
        if lenient:
            # neighbours of the ID itself and of every DOID in its equivalence class
            members = [ident]
            root = self.uf.find(ident)
            if not ident.startswith("DOID:"):
                members += self._doids_in(root)
            for m in members:
                for n in self.neighbours.get(m, ()):
                    out.add(self.uf.find(n))
        return out

    def _doids_in(self, root):
        if not hasattr(self, "_root_to_doids"):
            self._root_to_doids = defaultdict(list)
            for k in list(self.uf.parent):
                if k.startswith("DOID:"):
                    self._root_to_doids[self.uf.find(k)].append(k)
        return self._root_to_doids.get(root, [])

# ---------------------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------------------


def _open_table(path):
    opener = gzip.open if path.endswith(".gz") else open
    fh = opener(path, "rt", encoding="utf-8", errors="replace", newline="")
    sample = fh.read(4096)
    fh.seek(0)
    delim = "\t" if sample.count("\t") >= sample.count(",") else ","
    return fh, csv.DictReader(fh, delimiter=delim)


class DrugKey:
    """Drug identity: DrugBank ID when available, else normalised name."""

    @staticmethod
    def make(drugbank=None, name=None):
        db = norm_drugbank(drugbank)
        if db:
            return "DB:" + db
        n = norm_name(name)
        return "NAME:" + n if n else None


def read_triples(path, cols):
    """Return {relation: {drug_key: [(disease_id, disease_name, drug_label), ...]}} plus name index."""
    fh, rd = _open_table(path)
    missing = [c for c in (cols.drug_id, cols.relation, cols.disease_id) if c not in rd.fieldnames]
    if missing:
        sys.exit(f"Triples file is missing columns {missing}. Found: {rd.fieldnames}. "
                 f"Use --col-drug-id / --col-relation / --col-disease-id.")
    data = {IND: defaultdict(list), CI: defaultdict(list)}
    name_of = {}
    skipped = 0
    for row in rd:
        rel = (row.get(cols.relation) or "").strip()
        rel = {"indication": IND, "contraindication": CI}.get(rel.lower(), rel)
        if rel not in data:
            skipped += 1
            continue
        dname = row.get(cols.drug_name, "") if cols.drug_name else ""
        dbid = (row.get(cols.drugbank_id) if cols.drugbank_id else None) or row.get(cols.drug_id)
        key = DrugKey.make(dbid, None) or DrugKey.make(None, dname)
        dis = norm_id(row.get(cols.disease_id))
        if key is None or dis is None:
            skipped += 1
            continue
        name_of[key] = dname or row.get(cols.drug_id)
        # also index the name so name-only references can match
        data[rel][key].append((dis, row.get(cols.disease_name, "") if cols.disease_name else "",
                               norm_name(dname)))
    fh.close()
    if skipped:
        print(f"  [triples] skipped {skipped} rows (unknown relation, or unusable drug/disease ID)")
    return data, name_of


def read_pairs(path):
    """
    Two-column file of drug,disease pairs, with or without a header
    (graph_export.py: indicated.csv / contraindicated.csv; or Hetionet CtD
    pairs such as hetionet_indicated.csv). Returns {drug_key: {disease_id}}.
    """
    out = defaultdict(set)
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        delim = "\t" if sample.count("\t") > sample.count(",") else ","
        for row in csv.reader(fh, delimiter=delim):
            if len(row) < 2:
                continue
            key = DrugKey.make(row[0], None) or DrugKey.make(None, row[0])
            dis = norm_id(row[1])
            if key and dis:                       # a header row gives dis = None
                out[key].add(dis)
    return out


def read_pharmacotherapydb(path):
    """indications.tsv: doid_id, drugbank_id, disease, drug, category (DM/SYM/NOT)."""
    fh, rd = _open_table(path)
    gold = defaultdict(set)
    labels = {}
    for row in rd:
        if (row.get("category") or "").strip().upper() not in ("DM", "SYM"):
            continue
        key = DrugKey.make(row.get("drugbank_id"), row.get("drug"))
        dis = norm_id(row.get("doid_id"))
        if key and dis:
            gold[key].add(dis)
            labels[(key, dis)] = (row.get("drug", ""), row.get("disease", ""))
    fh.close()
    return {IND: gold}, labels


def read_hetionet(edges_path, nodes_path=None):
    """Hetionet v1.0 SIF edges: source, metaedge, target. CtD (treats) + CpD (palliates)."""
    names = {}
    if nodes_path:
        fh, rd = _open_table(nodes_path)
        for row in rd:
            names[row.get("id", "")] = row.get("name", "")
        fh.close()
    fh, rd = _open_table(edges_path)
    gold = defaultdict(set)
    labels = {}
    for row in rd:
        if row.get("metaedge") not in ("CtD", "CpD"):
            continue
        src, tgt = row.get("source", ""), row.get("target", "")
        key = DrugKey.make(src, None)
        dis = norm_id(tgt.split("::", 1)[-1])
        if key and dis:
            gold[key].add(dis)
            labels[(key, dis)] = (names.get(src, src), names.get(tgt, tgt))
    fh.close()
    return {IND: gold}, labels


def read_drugcentral(path):
    """DrugCentral export: drug_name, drugbank_id, relationship_name, concept_name, umls_cui, snomed_conceptid."""
    fh, rd = _open_table(path)
    gold = {IND: defaultdict(set), CI: defaultdict(set)}
    labels, unmapped_raw = {}, []
    for row in rd:
        rel = {"indication": IND, "contraindication": CI}.get(
            (row.get("relationship_name") or "").strip().lower())
        if rel is None:
            continue
        key = DrugKey.make(row.get("drugbank_id"), row.get("drug_name"))
        ids = [norm_id(row.get("umls_cui")),
               norm_id("SNOMED:" + row["snomed_conceptid"]) if row.get("snomed_conceptid") else None]
        ids = [i for i in ids if i]
        if not key:
            continue
        if not ids:
            unmapped_raw.append((rel, row.get("drug_name", ""), row.get("concept_name", "")))
            continue
        # keep the CUI as the representative; SNOMED is unioned in later
        gold[rel][key].add(tuple(ids))
        labels[(key, ids[0])] = (row.get("drug_name", ""), row.get("concept_name", ""))
    fh.close()
    return gold, labels, unmapped_raw

# ---------------------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------------------


def evaluate(pred_by_rel, gold_by_rel, onto, ref_name, restrict, gold_labels, pred_names,
             review_rows, unmapped_rows):
    rows = []
    for rel, gold in gold_by_rel.items():
        pred = pred_by_rel.get(rel, {})
        # name fallback: reference drug keyed by DrugBank but graph keyed by name (or vice versa)
        shared = set(pred) & set(gold)
        if not shared:
            print(f"  [{ref_name}/{rel}] no drugs in common -- check drug identifiers")
        for mode in ("strict", "lenient"):
            lenient = mode == "lenient"
            tp_p = fp = tp_r = fn = 0
            n_unmapped = 0
            for drug in sorted(shared):
                # gold clusters for this drug
                gold_items = []
                for g in gold[drug]:
                    ids = g if isinstance(g, tuple) else (g,)
                    known = [i for i in ids if i in onto.known]
                    if not known:
                        n_unmapped += 1
                        if mode == "strict":
                            lab = gold_labels.get((drug, ids[0]), ("", ""))
                            unmapped_rows.append([ref_name, rel, lab[0] or drug, ids[0], lab[1]])
                        continue
                    cl = set()
                    for i in known:
                        cl |= onto.clusters(i)
                    gold_items.append((ids[0], cl))
                gold_universe = set().union(*[c for _, c in gold_items]) if gold_items else set()
                # predicted items
                seen = set()
                pred_items = []
                for dis, dname, _ in pred[drug]:
                    if dis in seen:
                        continue
                    seen.add(dis)
                    cl = onto.clusters(dis, lenient)
                    if restrict and not (cl & REF_UNIVERSE[ref_name, rel]):
                        continue  # disease outside the reference vocabulary: not evaluable
                    pred_items.append((dis, dname, cl))
                # precision side
                for dis, dname, cl in pred_items:
                    if cl & gold_universe:
                        tp_p += 1
                    else:
                        fp += 1
                        if mode == "strict":
                            review_rows.append([ref_name, rel, "FP (in graph, not in reference)",
                                                pred_names.get(drug, drug), dis, dname])
                # recall side
                pred_universe = set().union(*[c for _, _, c in pred_items]) if pred_items else set()
                for gid, cl in gold_items:
                    if cl & pred_universe:
                        tp_r += 1
                    else:
                        fn += 1
                        if mode == "strict":
                            lab = gold_labels.get((drug, gid), ("", ""))
                            review_rows.append([ref_name, rel, "FN (in reference, not in graph)",
                                                lab[0] or pred_names.get(drug, drug), gid, lab[1]])
            p = tp_p / (tp_p + fp) if tp_p + fp else float("nan")
            r = tp_r / (tp_r + fn) if tp_r + fn else float("nan")
            f = 2 * p * r / (p + r) if (p == p and r == r and p + r) else float("nan")
            rows.append([ref_name, rel, mode, len(shared), tp_p, fp, tp_r, fn, n_unmapped,
                         round(p, 4), round(r, 4), round(f, 4)])
    return rows


REF_UNIVERSE = {}


def alias_by_name(pred, pred_names, labels):
    """Graph drugs keyed by name are re-keyed to the reference's DrugBank key when names match."""
    alias = {}
    for (key, _), (drug_name, _) in labels.items():
        n = norm_name(drug_name)
        if n:
            alias.setdefault("NAME:" + n, key)
    if not any(k.startswith("NAME:") for rel in pred.values() for k in rel):
        return pred, pred_names
    out, names = {}, dict(pred_names)
    for rel, by_drug in pred.items():
        out[rel] = defaultdict(list)
        for k, items in by_drug.items():
            k2 = alias.get(k, k)
            out[rel][k2].extend(items)
            names.setdefault(k2, pred_names.get(k, k))
    return out, names


def build_universe(ref_name, gold_by_rel, onto):
    for rel, gold in gold_by_rel.items():
        u = set()
        for items in gold.values():
            for g in items:
                for i in (g if isinstance(g, tuple) else (g,)):
                    if i in onto.known:
                        u |= onto.clusters(i)
        REF_UNIVERSE[ref_name, rel] = u


def cmd_evaluate(a):
    os.makedirs(a.out, exist_ok=True)
    onto = Ontologies()
    for p in a.obo:
        print(f"Loading ontology {p}")
        onto.load_obo(p)
    print(f"  {len(onto.known):,} identifiers known")
    sizes = defaultdict(int)
    for k in onto.known:
        sizes[onto.uf.find(k)] += 1
    big = max(sizes.values()) if sizes else 0
    print(f"  largest equivalence class: {big} identifiers"
          + ("  <-- suspiciously large; check xrefs" if big > 25 else ""))

    if a.triples:
        print(f"Reading triples {a.triples}")
        pred, pred_names = read_triples(a.triples, a)
    else:
        pred, pred_names = {IND: defaultdict(list), CI: defaultdict(list)}, {}
        for rel, path in ((IND, a.indicated), (CI, a.contraindicated)):
            if not path:
                continue
            print(f"Reading {rel} pairs {path}")
            for key, diseases in read_pairs(path).items():
                pred_names[key] = key.split(":", 1)[1]
                pred[rel][key] = [(d, "", "") for d in sorted(diseases)]
    for rel in (IND, CI):
        print(f"  {rel}: {sum(len(v) for v in pred[rel].values()):,} triples, {len(pred[rel]):,} drugs")
    unknown = {d for rel in pred.values() for v in rel.values() for d, _, _ in v if d not in onto.known}
    if unknown:
        print(f"  warning: {len(unknown)} graph disease IDs are not in the loaded ontologies "
              f"(add hp.obo / mondo.obo, or check the ID format), e.g. {sorted(unknown)[:3]}")

    refs = []
    if a.pharmacotherapydb:
        g, lab = read_pharmacotherapydb(a.pharmacotherapydb)
        refs.append(("PharmacotherapyDB", g, lab, not a.no_restrict))
    if a.hetionet:
        if not a.hetionet_nodes:
            print("  note: without --hetionet-nodes, graph drugs without a DrugBank ID cannot be matched to Hetionet by name")
        g, lab = read_hetionet(a.hetionet, a.hetionet_nodes)
        refs.append(("Hetionet", g, lab, not a.no_restrict))
    if a.hetionet_pairs:
        g = {IND: read_pairs(a.hetionet_pairs)}
        lab = {}
        refs.append(("Hetionet", g, lab, not a.no_restrict))
    if a.drugcentral:
        g, lab, unm = read_drugcentral(a.drugcentral)
        refs.append(("DrugCentral", g, lab, a.restrict_drugcentral))
    if not refs:
        sys.exit("Give at least one reference: --pharmacotherapydb, --hetionet, --hetionet-pairs or --drugcentral")

    metrics, review, unmapped = [], [], []
    for name, gold, labels, restrict in refs:
        print(f"Evaluating against {name} (restrict to reference diseases: {restrict})")
        build_universe(name, gold, onto)
        p2, n2 = alias_by_name(pred, pred_names, labels)
        metrics += evaluate(p2, gold, onto, name, restrict, labels, n2, review, unmapped)

    hdr = ["reference", "relation", "matching", "shared_drugs", "TP_precision", "FP",
           "TP_recall", "FN", "reference_unmapped", "precision", "recall", "F1"]
    with open(os.path.join(a.out, "metrics.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(hdr)
        w.writerows(metrics)

    random.seed(a.seed)
    sample = []
    by_group = defaultdict(list)
    for r in review:
        by_group[(r[0], r[1], r[2])].append(r)
    for grp, rows in sorted(by_group.items()):
        sample += random.sample(rows, min(a.review_per_group, len(rows)))
    with open(os.path.join(a.out, "disagreements.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["reference", "relation", "type", "drug", "disease_id", "disease_name",
                    "annotator_A", "annotator_B", "category", "notes"])
        for r in sample:
            w.writerow(r + ["", "", "", ""])
    with open(os.path.join(a.out, "unmapped.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["reference", "relation", "drug", "reference_disease_id", "reference_disease_name"])
        w.writerows(unmapped)

    print("\nRESULTS")
    print(f"{'reference':<18}{'relation':<22}{'mode':<9}{'drugs':>6}{'P':>8}{'R':>8}{'F1':>8}")
    for m in metrics:
        print(f"{m[0]:<18}{m[1]:<22}{m[2]:<9}{m[3]:>6}{m[9]:>8}{m[10]:>8}{m[11]:>8}")
    print(f"\nWrote {a.out}/metrics.csv, disagreements.csv ({len(sample)} rows to review), unmapped.csv")


def cmd_kappa(a):
    """Cohen's kappa between annotator_A and annotator_B (any categorical labels)."""
    fh, rd = _open_table(a.file)
    pairs = [((r.get(a.col_a) or "").strip().lower(), (r.get(a.col_b) or "").strip().lower())
             for r in rd]
    fh.close()
    pairs = [(x, y) for x, y in pairs if x and y]
    n = len(pairs)
    if n == 0:
        sys.exit("No rows with both annotations filled in.")
    cats = sorted({c for p in pairs for c in p})
    po = sum(x == y for x, y in pairs) / n
    pe = sum((sum(x == c for x, _ in pairs) / n) * (sum(y == c for _, y in pairs) / n) for c in cats)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    print(f"Rows annotated by both: {n}")
    print(f"Categories: {cats}")
    print(f"Observed agreement: {po:.3f}   Expected: {pe:.3f}   Cohen's kappa: {kappa:.3f}")
    # confusion table
    print("\nConfusion (rows = annotator A, columns = annotator B)")
    print(" " * 22 + "".join(f"{c[:12]:>14}" for c in cats))
    for c in cats:
        print(f"{c[:20]:<22}" + "".join(f"{sum(x == c and y == d for x, y in pairs):>14}" for d in cats))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("evaluate", help="compare triples with reference resources")
    e.add_argument("--triples", help="triples file with a header (see INPUT 1)")
    e.add_argument("--indicated", help="graph export indicated.csv (drug,disease pairs)")
    e.add_argument("--contraindicated", help="graph export contraindicated.csv (drug,disease pairs)")
    e.add_argument("--obo", action="append", required=True, help="OBO file (repeatable); doid.obo required")
    e.add_argument("--pharmacotherapydb")
    e.add_argument("--hetionet", help="hetionet-v1.0-edges.sif(.gz)")
    e.add_argument("--hetionet-nodes", help="hetionet-v1.0-nodes.tsv (for readable names)")
    e.add_argument("--hetionet-pairs", help="Hetionet CtD as drug,disease pairs (e.g. hetionet_indicated.csv)")
    e.add_argument("--drugcentral", help="CSV exported with the SQL query in the header")
    e.add_argument("--out", default="results")
    e.add_argument("--no-restrict", action="store_true",
                   help="do not restrict predictions to diseases covered by PharmacotherapyDB/Hetionet")
    e.add_argument("--restrict-drugcentral", action="store_true",
                   help="also restrict predictions to diseases covered by DrugCentral")
    e.add_argument("--review-per-group", type=int, default=25,
                   help="disagreements sampled per reference x relation x FP/FN (default 25)")
    e.add_argument("--seed", type=int, default=42)
    e.add_argument("--col-drug-id", dest="drug_id", default="drug_id")
    e.add_argument("--col-relation", dest="relation", default="relation")
    e.add_argument("--col-disease-id", dest="disease_id", default="disease_id")
    e.add_argument("--col-drug-name", dest="drug_name", default="drug_name")
    e.add_argument("--col-disease-name", dest="disease_name", default="disease_name")
    e.add_argument("--col-drugbank-id", dest="drugbank_id", default="drugbank_id")
    e.set_defaults(func=cmd_evaluate)

    k = sub.add_parser("kappa", help="Cohen's kappa for the manual review")
    k.add_argument("--file", required=True)
    k.add_argument("--col-a", default="annotator_A")
    k.add_argument("--col-b", default="annotator_B")
    k.set_defaults(func=cmd_kappa)

    a = ap.parse_args()
    if a.cmd == "evaluate" and not a.triples and not (a.indicated or a.contraindicated):
        sys.exit("Give --triples, or --indicated / --contraindicated")
    if a.cmd == "evaluate" and a.triples:
        # optional columns that are absent are simply ignored
        fh, rd = _open_table(a.triples)
        present = set(rd.fieldnames or [])
        fh.close()
        for opt in ("drug_name", "disease_name", "drugbank_id"):
            if getattr(a, opt) not in present:
                setattr(a, opt, None)
    a.func(a)


if __name__ == "__main__":
    main()
