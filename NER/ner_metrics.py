"""
NER metrics: collect what a NER run did and save it as one JSON report.

The report records, for one run:
  - the version of each ontology used (read from the <name>_version.txt files
    written by process_ontology.sh), so the results can be reproduced;
  - for each processed file, how many entities of each kind were found;
  - totals over the run, including the distinct drugs and diseases (stage S2
    of the dataflow table in the paper);
  - processing times.

Safe to use from several threads (the batch uses a ThreadPoolExecutor).
"""

import json
import threading
import time
from functools import wraps
from pathlib import Path
from typing import Dict, Optional

# Entity lists written by process_disease_data, and the ID key inside each entity
DISEASE_LISTS = {
    'doid_entities': 'doid_id',
    'orphanet_entities': 'orphanet_id',
    'hpo_entities': 'hpo_id',
}
SECTIONS = ('indications', 'contraindications')


def count_entities(data: Dict) -> Dict:
    """
    Count the entities in one NER output record.

    Returns per-record counts plus the sets of IDs found, so that the run
    totals can count distinct drugs and diseases.
    """
    counts = {'drug_drugbank': 0, 'drug_chebi': 0, 'drug_no_id': 0}
    drug_ids, disease_ids = set(), set()
    relations = {section: set() for section in SECTIONS}

    for drug in data.get('drug', []) or []:
        if drug.get('drugbank_id'):
            counts['drug_drugbank'] += 1
            drug_ids.add(drug['drugbank_id'])
        elif drug.get('chebi_id'):
            counts['drug_chebi'] += 1
            drug_ids.add(drug['chebi_id'])
        else:
            counts['drug_no_id'] += 1

    for section in SECTIONS:
        value = data.get(section)
        if not isinstance(value, dict):
            continue
        for list_key, id_key in DISEASE_LISTS.items():
            entities = value.get(list_key) or []
            counts[f'{section}.{list_key}'] = len(entities)
            for entity in entities:
                if isinstance(entity, dict) and entity.get(id_key):
                    disease_ids.add(entity[id_key])
                    relations[section].add(entity[id_key])

    counts['entities_found'] = sum(
        v for k, v in counts.items() if k != 'drug_no_id')
    return {'counts': counts, 'drug_ids': drug_ids,
            'disease_ids': disease_ids, 'relations': relations}


def read_ontology_versions(data_dir: str) -> Dict[str, Dict[str, str]]:
    """Read every <name>_version.txt in data_dir (written by process_ontology.sh)."""
    versions = {}
    for path in sorted(Path(data_dir).glob('*_version.txt')):
        info = {}
        for line in path.read_text(encoding='utf-8').splitlines():
            key, _, value = line.partition('\t')
            if key:
                info[key] = value
        versions[path.name[:-len('_version.txt')]] = info
    return versions


class NERMetrics:
    """Collect and report NER processing metrics"""

    def __init__(self):
        self._lock = threading.Lock()
        self._drug_ids = set()
        self._disease_ids = set()
        self._relations = {section: set() for section in SECTIONS}
        self._started = time.time()
        self.metrics = {
            'ontology_versions': {},
            'ontology_downloads': {},
            'file_processing': {},
            'failed_files': {},
            'entity_counts': {},
            'processing_times': {},
        }

    def record_ontology_versions(self, data_dir: str):
        """Record the version of each ontology found in data_dir"""
        versions = read_ontology_versions(data_dir)
        with self._lock:
            self.metrics['ontology_versions'] = versions
        return versions

    def record_ontology_download(self, name: str, success: bool, duration: float):
        """Record ontology download metrics"""
        with self._lock:
            self.metrics['ontology_downloads'][name] = {
                'success': success,
                'duration_seconds': round(duration, 3),
                'timestamp': time.time(),
            }

    def record_file_processing(self, file_path: str, duration: float,
                               data: Optional[Dict] = None,
                               entities_found: Optional[int] = None):
        """
        Record file processing metrics.

        Pass the processed record as `data` to count its entities by kind;
        `entities_found` alone still works as before.
        """
        details = count_entities(data) if data is not None else None
        entry = {'duration_seconds': round(duration, 3), 'timestamp': time.time()}
        if details:
            entry.update(details['counts'])
        else:
            entry['entities_found'] = entities_found or 0

        with self._lock:
            self.metrics['file_processing'][file_path] = entry
            if details:
                self._drug_ids |= details['drug_ids']
                self._disease_ids |= details['disease_ids']
                for section in SECTIONS:
                    # (drug, disease) pairs = relations of the graph
                    for drug_id in details['drug_ids']:
                        for disease_id in details['relations'][section]:
                            self._relations[section].add((drug_id, disease_id))
                for key, value in details['counts'].items():
                    totals = self.metrics['entity_counts']
                    totals[key] = totals.get(key, 0) + value

    def record_failure(self, file_path: str, error: str):
        """Record a file that could not be processed"""
        with self._lock:
            self.metrics['failed_files'][file_path] = str(error)

    def record_time(self, name: str, duration: float):
        """Record the duration of a named step (accumulates over calls)"""
        with self._lock:
            entry = self.metrics['processing_times'].setdefault(
                name, {'calls': 0, 'total_seconds': 0.0})
            entry['calls'] += 1
            entry['total_seconds'] = round(entry['total_seconds'] + duration, 3)

    def save_report(self, output_path: str):
        """Save metrics report as JSON"""
        with self._lock:
            files = self.metrics['file_processing']
            report = {
                'summary': {
                    'total_files_processed': len(files),
                    'total_files_failed': len(self.metrics['failed_files']),
                    'total_ontologies': len(self.metrics['ontology_versions'])
                                        or len(self.metrics['ontology_downloads']),
                    'total_entities': sum(m.get('entities_found', 0) for m in files.values()),
                    'distinct_drugs': len(self._drug_ids),
                    'distinct_diseases': len(self._disease_ids),
                    'drug_disease_indications': len(self._relations['indications']),
                    'drug_disease_contraindications': len(self._relations['contraindications']),
                    'total_processing_time': round(
                        sum(m['duration_seconds'] for m in files.values()), 3),
                    'wall_clock_seconds': round(time.time() - self._started, 3),
                },
                'details': self.metrics,
            }
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        return report


# Decorator for timing functions
def timed_metric(metrics_collector: NERMetrics, metric_name: str):
    """Decorator to time function execution and record it in the collector"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start
                metrics_collector.record_time(metric_name, duration)
                print(f"{metric_name} completed in {duration:.2f}s")
        return wrapper
    return decorator