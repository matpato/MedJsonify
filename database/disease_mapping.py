"""
One node per disease: map Orphanet (ORDO) and HPO identifiers to the
equivalent Disease Ontology (DO) identifier, when there is one.

NER links each mention to DO, then ORDO, then HPO, so the same disease can be
linked to DO in one label and to ORDO or HPO in another (e.g. two "urinary
tract infection" nodes). Two mappings bring them together, in this order:

  1. by name: the mention, or the ORDO/HPO term, has exactly the name (or a
     synonym) of a DO term -- read from doid_links.tsv, the DO lexicon NER uses;
     plural forms are tried too ("infections" -> "infection");
  2. by cross-reference: the ORDO/HPO term and one DO term share a database
     cross-reference (UMLS, MeSH, OMIM, MONDO, or DO's own ORDO references) and
     no other DO term shares it.

The result is cached in <data_dir>/disease_equivalences.tsv (built from the
.owl files the first time; delete the file to rebuild it).

    python3 disease_mapping.py            # build the cache and print a summary
"""

import os
import re
import sys
import threading
import xml.etree.ElementTree as ET
from collections import defaultdict

DATA_DIR = os.environ.get('NER_DATA_DIR', '/opt/airflow/dags/NER/ontologies/data')
CACHE_NAME = 'disease_equivalences.tsv'

_RDF = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}'
_OWL = '{http://www.w3.org/2002/07/owl#}'
_OBO = '{http://www.geneontology.org/formats/oboInOwl#}'

# Cross-reference prefixes, written in several ways by the ontologies
_XREF_PREFIX = {
    'MESH': 'MESH', 'MSH': 'MESH', 'MeSH': 'MESH',
    'UMLS': 'UMLS', 'UMLS_CUI': 'UMLS',
    'OMIM': 'OMIM', 'MIM': 'OMIM',
    'MONDO': 'MONDO',
    'ORDO': 'ORPHA', 'Orphanet': 'ORPHA', 'ORPHA': 'ORPHA', 'ORPHANET': 'ORPHA',
}

_lock = threading.Lock()
_cache = {}


def norm_name(text):
    """Same normalisation as process_ontology.sh (lower case, other characters -> '.')."""
    text = re.sub(r'\s*\((?:DOID|HP|ORPHA)[:_][^)]*\)\s*$', '', str(text or ''))
    text = re.sub(r'[^a-z0-9 ]', '.', text.lower())
    return re.sub(r'\s+', ' ', text).strip()


def _singular_forms(name):
    """'urinary tract infections' -> ['urinary tract infection', ...]."""
    forms = [name]
    if name.endswith('ies'):
        forms.append(name[:-3] + 'y')
    if name.endswith('es'):
        forms.append(name[:-2])
    if name.endswith('s') and not name.endswith('ss'):
        forms.append(name[:-1])
    return forms


def _curie(uri):
    last = uri.rstrip('/').rsplit('/', 1)[-1]
    m = re.match(r'^(DOID|HP|Orphanet)_(\d+)$', last)
    if not m:
        return None
    return f'Orphanet_{m.group(2)}' if m.group(1) == 'Orphanet' else f'{m.group(1)}:{m.group(2)}'


def _xref_key(text):
    if not text or ':' not in text:
        return None
    prefix, _, local = text.strip().partition(':')
    prefix = _XREF_PREFIX.get(prefix.strip())
    local = local.strip().upper()
    return f'{prefix}:{local}' if prefix and local else None


def _read_owl(path, want_prefix):
    """{curie: (label, {xref keys})} for the classes of one ontology."""
    terms = {}
    if not os.path.exists(path):
        print(f"WARNING: {path} not found -- cross-references of this ontology not used")
        return terms
    for _, elem in ET.iterparse(path, events=('end',)):
        if elem.tag in (_OWL + 'Class', 'Class') or elem.tag.endswith('}Class'):
            curie = _curie(elem.get(_RDF + 'about') or '')
            if curie and curie.startswith(want_prefix):
                deprecated = any(c.tag == _OWL + 'deprecated' and (c.text or '').strip() == 'true'
                                 for c in elem)
                if not deprecated:
                    label = next((c.text for c in elem if c.tag.endswith('}label') and c.text), '')
                    keys = {k for k in (_xref_key(c.text) for c in elem if c.tag == _OBO + 'hasDbXref')
                            if k}
                    if curie.startswith('Orphanet_'):
                        keys.add('ORPHA:' + curie.split('_')[1])      # matches DO's "ORDO:nnn"
                    terms[curie] = (label, keys)
            elem.clear()
    return terms


def _read_doid_lexicon(data_dir):
    """normalised DO label or synonym -> DO id (only names that point to one DO term)."""
    path = os.path.join(data_dir, 'doid_links.tsv')
    names = defaultdict(set)
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            label, _, uri = line.rstrip('\n').partition('\t')
            curie = _curie(uri)
            if label and curie:
                names[label.strip()].add(curie)
    else:
        print(f"WARNING: {path} not found -- mapping by name not used")
    return {n: ids.pop() for n, ids in names.items() if len(ids) == 1}


def build(data_dir=DATA_DIR):
    """Build {ORDO/HPO id: DO id} from the .owl files, and write the cache."""
    doid = _read_owl(os.path.join(data_dir, 'doid.owl'), 'DOID:')
    by_key = defaultdict(set)
    for curie, (_, keys) in doid.items():
        for k in keys:
            by_key[k].add(curie)
    doid_names = _read_doid_lexicon(data_dir)

    mapping, how = {}, {}
    for fname, prefix in (('ordo.owl', 'Orphanet_'), ('hpo.owl', 'HP:')):
        for curie, (label, keys) in _read_owl(os.path.join(data_dir, fname), prefix).items():
            target = None
            for form in _singular_forms(norm_name(label)):
                if form in doid_names:
                    target, method = doid_names[form], 'name'
                    break
            if not target:
                candidates = set().union(*(by_key[k] for k in keys if k in by_key)) if keys else set()
                if len(candidates) == 1:
                    target, method = candidates.pop(), 'xref'
            if target:
                mapping[curie], how[curie] = target, method

    path = os.path.join(data_dir, CACHE_NAME)
    with open(path, 'w', encoding='utf-8') as f:
        for src in sorted(mapping):
            f.write(f'{src}\t{mapping[src]}\t{how[src]}\n')
    n_orpha = sum(1 for k in mapping if k.startswith('Orphanet_'))
    print(f"Disease equivalences: {n_orpha} ORDO and {len(mapping) - n_orpha} HPO terms mapped to DO "
          f"({sum(1 for v in how.values() if v == 'name')} by name, "
          f"{sum(1 for v in how.values() if v == 'xref')} by cross-reference; "
          f"{len(doid)} DO terms, {len(by_key)} DO cross-references read) -> {CACHE_NAME}")
    return mapping


def _load(data_dir):
    with _lock:
        if data_dir not in _cache:
            path = os.path.join(data_dir, CACHE_NAME)
            if os.path.exists(path):
                mapping = {}
                for line in open(path, encoding='utf-8'):
                    parts = line.rstrip('\n').split('\t')
                    if len(parts) >= 2:
                        mapping[parts[0]] = parts[1]
            else:
                mapping = build(data_dir)
            _cache[data_dir] = (mapping, _read_doid_lexicon(data_dir))
        return _cache[data_dir]


def canonical_disease(disease_id, mention=None, data_dir=DATA_DIR):
    """
    The DO id for an ORDO/HPO disease when an equivalent exists, else the id unchanged.
    `mention` (the text that was linked) is also tried against the DO names.
    """
    if not disease_id or disease_id.startswith('DOID:'):
        return disease_id
    mapping, doid_names = _load(data_dir)
    if disease_id in mapping:
        return mapping[disease_id]
    if mention:
        for form in _singular_forms(norm_name(mention)):
            if form in doid_names:
                return doid_names[form]
    return disease_id


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else DATA_DIR)