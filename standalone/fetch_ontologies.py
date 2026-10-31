"""
Download and process the ontologies listed in bioner.ini (standalone mode).

For each lexicon in [ONTO] active_lexicons, this reads <name>_url and
<name>_name from [ONTOLOGIES], downloads the file, unzips it if it is a .zip,
saves it as <name>.owl in the ontology data folder, and runs the project's
process_ontology.sh on it. The lexicon files (<name>_links.tsv, ...) and
<name>_version.txt are then exactly what NER expects. For HPO it also writes
hpo_phenotypes.txt: the terms under Phenotypic abnormality (HP:0000118), the
only HPO terms NER links as diseases.

Ontologies that are already processed (<name>_links.tsv exists) are skipped,
unless --force is given or [ONTO] update = 1.

    python3 fetch_ontologies.py                    # paths from bioner.ini
    python3 fetch_ontologies.py --force            # download and process again
    python3 fetch_ontologies.py --only ordo chebi  # just these
"""

import argparse
import configparser
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
import gzip

DEFAULT_INI = '/opt/airflow/dags/NER/bioner.ini'
ALIASES = {'hp': 'hpo'}          # active_lexicons may say hp; the keys say hpo


def read_config(ini_path):
    cfg = configparser.ConfigParser()
    if not cfg.read(ini_path):
        raise SystemExit(f"ERROR: cannot read {ini_path}")
    active = [ALIASES.get(x.strip().lower(), x.strip().lower())
              for x in cfg.get('ONTO', 'active_lexicons', fallback='').split(',') if x.strip()]
    update = cfg.get('ONTO', 'update', fallback='0').strip() == '1'
    data_dir = cfg.get('STANDALONE_NER', 'data_dir', fallback='/opt/airflow/dags/NER/ontologies/data')
    scripts_dir = cfg.get('STANDALONE_NER', 'scripts_dir', fallback='/opt/airflow/dags/NER/ontologies/scripts')
    ontologies = {}
    for key in active:
        url = cfg.get('ONTOLOGIES', f'{key}_url', fallback='').strip()
        name = cfg.get('ONTOLOGIES', f'{key}_name', fallback=key).strip() or key
        ontologies[key] = {'url': url, 'name': name}
    return ontologies, update, data_dir, scripts_dir


def download(url, target):
    """Download url to target (follows redirects), with a simple progress line."""
    if '#' in url:
        raise ValueError(f"URL contains '#': {url} -- keep only one URL in bioner.ini")
    req = urllib.request.Request(url, headers={'User-Agent': 'MedJsonify/standalone'})
    start = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp, open(target, 'wb') as out:
        total = int(resp.headers.get('Content-Length') or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done / 1e6:7.1f} / {total / 1e6:.1f} MB", end='', flush=True)
            else:
                print(f"\r  {done / 1e6:7.1f} MB", end='', flush=True)
    print(f"  ({time.time() - start:.0f}s)")


def extract_owl(downloaded, url, target):
    """Turn the download into a single .owl file at target."""
    if zipfile.is_zipfile(downloaded):
        with zipfile.ZipFile(downloaded) as z:
            owls = [n for n in z.namelist() if n.lower().endswith('.owl') and not n.startswith('__MACOSX')]
            if not owls:
                raise ValueError(f"no .owl file inside {os.path.basename(url)}: {z.namelist()}")
            member = max(owls, key=lambda n: z.getinfo(n).file_size)
            print(f"  unzipped {member}")
            with z.open(member) as src, open(target, 'wb') as dst:
                shutil.copyfileobj(src, dst)
    elif url.lower().endswith('.gz'):
        with gzip.open(downloaded, 'rb') as src, open(target, 'wb') as dst:
            shutil.copyfileobj(src, dst)
        print("  gunzipped")
    else:
        shutil.move(downloaded, target)


def process(name, data_dir, scripts_dir):
    script = os.path.join(scripts_dir, 'process_ontology.sh')
    result = subprocess.run(['bash', script, f'{name}.owl', '.'], cwd=data_dir,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    keep = [l for l in result.stdout.splitlines()
            if any(w in l for w in ('ERROR', 'WARNING', 'Version', 'Extracted', 'Total entities'))]
    for line in keep:
        print('  ' + line.replace('\x1b[0;31m', '').replace('\x1b[0;32m', '')
              .replace('\x1b[1;33m', '').replace('\x1b[0;34m', '').replace('\x1b[0m', ''))
    if result.returncode != 0:
        print(result.stdout[-2000:])
        raise RuntimeError(f"process_ontology.sh failed for {name}.owl (exit {result.returncode})")


HPO_PHENOTYPE_ROOT = 'HP_0000118'   # Phenotypic abnormality
_RDF = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}'
_RDFS = '{http://www.w3.org/2000/01/rdf-schema#}'
_OWL = '{http://www.w3.org/2002/07/owl#}'


def build_hpo_phenotypes(owl_path, out_path, root=HPO_PHENOTYPE_ROOT):
    """
    Write the HPO terms under Phenotypic abnormality (HP:0000118), one per
    line as HP:nnnnnnn, using the rdfs:subClassOf links in hp.owl. NER links
    only these HPO terms as diseases; the other HPO branches (clinical
    modifiers such as 'chronic' or 'severe', clinical course, mode of
    inheritance, frequency) are not diseases.
    """
    import xml.etree.ElementTree as ET
    children = {}
    for _, elem in ET.iterparse(owl_path, events=('end',)):
        if elem.tag == _OWL + 'Class':
            about = elem.get(_RDF + 'about') or ''
            if 'HP_' in about:
                child = about.rsplit('/', 1)[-1]
                for sub in elem.findall(_RDFS + 'subClassOf'):
                    parent = (sub.get(_RDF + 'resource') or '').rsplit('/', 1)[-1]
                    if parent.startswith('HP_'):
                        children.setdefault(parent, []).append(child)
            elem.clear()
    keep, todo = set(), list(children.get(root, []))
    while todo:
        term = todo.pop()
        if term not in keep:
            keep.add(term)
            todo.extend(children.get(term, []))
    with open(out_path, 'w', encoding='utf-8') as f:
        for term in sorted(keep):
            f.write(term.replace('_', ':') + '\n')
    print(f"  {len(keep)} HPO phenotype terms (under {root.replace('_', ':')}) -> {os.path.basename(out_path)}")
    return len(keep)


def version_of(name, data_dir):
    path = os.path.join(data_dir, f'{name}_version.txt')
    if not os.path.exists(path):
        return ''
    info = dict(l.split('\t', 1) for l in open(path, encoding='utf-8').read().splitlines() if '\t' in l)
    return info.get('version_iri') or info.get('version_info') or info.get('data_version') or ''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ini', default=DEFAULT_INI)
    ap.add_argument('--force', action='store_true', help='download and process again')
    ap.add_argument('--only', nargs='+', help='only these lexicons (e.g. ordo chebi)')
    args = ap.parse_args()

    ontologies, update, data_dir, scripts_dir = read_config(args.ini)
    force = args.force or update
    if args.only:
        wanted = [ALIASES.get(o.lower(), o.lower()) for o in args.only]
        ontologies = {k: v for k, v in ontologies.items() if k in wanted}
    os.makedirs(data_dir, exist_ok=True)

    print(f"Ontologies: {', '.join(ontologies) or 'none'}  (force: {'yes' if force else 'no'})")
    print(f"Data folder: {data_dir}")
    failed = []
    rebuilt = False          # True when an ontology is downloaded/processed in this run
    for key, onto in ontologies.items():
        name, url = onto['name'], onto['url']
        print(f"\n--- {name} ---")
        if not force and os.path.exists(os.path.join(data_dir, f'{name}_links.tsv')):
            print(f"  already processed -- skipped (use --force or update = 1 to redo)")
            continue
        if not url:
            print(f"  ERROR: no {key}_url in [ONTOLOGIES] of {args.ini}")
            failed.append(name)
            continue
        print(f"  {url}")
        tmp = tempfile.NamedTemporaryFile(dir=data_dir, prefix=f'.{name}_', delete=False)
        tmp.close()
        try:
            download(url, tmp.name)
            extract_owl(tmp.name, url, os.path.join(data_dir, f'{name}.owl'))
            process(name, data_dir, scripts_dir)
            rebuilt = True
        except Exception as e:
            print(f"  ERROR: {e}")
            failed.append(name)
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)

    # HPO: list of the terms that NER may link as diseases (built from hpo.owl,
    # also when HPO itself was already processed)
    for key, onto in ontologies.items():
        if key != 'hpo':
            continue
        owl = os.path.join(data_dir, f"{onto['name']}.owl")
        out = os.path.join(data_dir, 'hpo_phenotypes.txt')
        if os.path.exists(owl) and (force or not os.path.exists(out)):
            print("\n--- hpo phenotype list ---")
            try:
                build_hpo_phenotypes(owl, out)
            except Exception as e:
                print(f"  ERROR building {os.path.basename(out)}: {e}")
                failed.append('hpo_phenotypes')
        elif not os.path.exists(owl) and not os.path.exists(out):
            print(f"\nWARNING: {owl} not found -- cannot build hpo_phenotypes.txt "
                  "(NER will keep all HPO terms)")

    # Disease equivalences (ORDO/HPO -> DO), used when the graph is built
    # (database/disease_mapping.py); rebuilt when the ontologies change
    mapping_code = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(scripts_dir))),
                                'database', 'disease_mapping.py')
    cache = os.path.join(data_dir, 'disease_equivalences.tsv')
    if os.path.exists(mapping_code) and (force or not os.path.exists(cache) or rebuilt):
        print("\n--- disease equivalences (ORDO/HPO -> DO) ---")
        result = subprocess.run([sys.executable, mapping_code, data_dir],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        print('  ' + result.stdout.strip().replace('\n', '\n  '))
        if result.returncode != 0:
            failed.append('disease_equivalences')

    print("\nLexicons in the data folder:")
    for key, onto in ontologies.items():
        name = onto['name']
        ok = os.path.exists(os.path.join(data_dir, f'{name}_links.tsv'))
        print(f"  {name:<6} {'OK     ' if ok else 'MISSING'} {version_of(name, data_dir)}")
    if failed:
        print(f"\nFAILED: {', '.join(failed)}")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())