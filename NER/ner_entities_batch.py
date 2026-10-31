"""
Named Entities Batch Processing (Updated for Standalone NER)
============================
Objective: Process multiple drug data files in batch mode, enriching them with entity identifiers 
from various ontologies (ChEBI, DrugBank, DOID, Orphanet) using parallelized processing.

Updated to use standalone_bioner.py with shell scripts instead of MER.

This script:
1. Loads ontology data using standalone_bioner
2. Processes all JSON files in a directory tree
3. Adds ontology identifiers to drugs and diseases
4. Performs concurrent processing for better performance
"""

import os
import json
import configparser
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List

from tenacity import retry, stop_after_attempt, wait_exponential
from NER.logging_config import setup_logging

import time
from NER.ner_metrics import NERMetrics

# Import updated modules
try:
    # Try relative imports first (when used as a package)
    from .ner_entities import process_drug_data, process_disease_data
    from .ner_drugbank import load_drugbank_data, create_vocabulary
    from .standalone_bioner import StandaloneBioNER
except ImportError:
    # Fall back to direct imports (when used as standalone scripts)
    from ner_entities import process_drug_data, process_disease_data
    from ner_drugbank import load_drugbank_data, create_vocabulary
    from standalone_bioner import StandaloneBioNER

# ---------------------------------------------------------------------------------------- #
# Orphanet/ORDO Processing Functions
# ---------------------------------------------------------------------------------------- #

def build_disease_dictionary_from_lexicon(data_dir: str, lexicon_name: str = 'ordo') -> Dict[str, str]:
    """
    Build disease dictionary from processed lexicon files.
    
    Args:
        data_dir (str): Directory containing lexicon files
        lexicon_name (str): Name of lexicon (default: 'ordo')
        
    Returns:
        Dictionary mapping disease names to Orphanet URIs
    """
    links_file = Path(data_dir) / f"{lexicon_name}_links.tsv"
    
    if not links_file.exists():
        print(f"WARNING: Links file not found: {links_file}")
        return {}
    
    disease_dict = {}
    
    try:
        with open(links_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    # parts[0] is the normalized disease name (lowercase, dots for special chars)
                    # parts[1] is the URI
                    disease_name = parts[0].strip()
                    uri = parts[1].strip()
                    disease_dict[disease_name] = uri
        
        print(f"Built disease dictionary with {len(disease_dict)} entries from {lexicon_name}")
        return disease_dict
    
    except Exception as e:
        print(f"ERROR building disease dictionary: {e}")
        return {}

# ---------------------------------------------------------------------------------------- #
# File Processing Functions
# ---------------------------------------------------------------------------------------- #
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def process_drug_file_with_retry(file_path, *args):
    """Process drug file with automatic retry on failure"""
    try:
        return process_drug_file(file_path, *args)
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        raise

def process_drug_file(file_path,
                      output_dir,
                      drugbank,
                      vocabulary,
                      disease_terms,
                      data_dir,
                      scripts_dir,
                      metrics=None):
    """
    Process a single drug data file.

    Args:
        file_path (str): Path to input JSON file
        output_dir (str): Directory to save output file
        drugbank (DataFrame): DrugBank reference data
        vocabulary (set): Drug name vocabulary for matching
        disease_terms (dict): Disease term dictionary from ORDO
        data_dir (str): Directory containing ontology data
        scripts_dir (str): Directory containing shell scripts
        metrics (NERMetrics, optional): Collector for the run's metrics
    """
    start = time.time()

    # Load the input file and add drugs, then diseases
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            drug_data = json.load(f)
        processed_data = process_drug_data(drug_data, drugbank, vocabulary, disease_terms,
                                           data_dir=data_dir, scripts_dir=scripts_dir)
        processed_data = process_disease_data(processed_data,
                                              data_dir=data_dir, scripts_dir=scripts_dir)
    except Exception as e:
        print(f"ERROR processing {file_path}: {e}")
        if metrics:
            metrics.record_failure(file_path, e)
        return

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Save the processed data
    output_path = os.path.join(output_dir, os.path.basename(file_path))
    print(f"Saving processed data to: {output_path}")
    try:
        with open(output_path, 'w', encoding='utf-8') as f_out:
            json.dump(processed_data, f_out, indent=4)
        print(f"File saved: {output_path}")
    except Exception as e:
        print(f"ERROR saving {output_path}: {e}")
        if metrics:
            metrics.record_failure(file_path, f"save failed: {e}")
        return

    # Count the file only once it has been saved
    if metrics:
        metrics.record_file_processing(file_path, time.time() - start, data=processed_data)
    

def process_file_in_batch(args):
    """
    Process a single file as part of batch processing.
    This function is called from ThreadPoolExecutor.

    Args:
        args (tuple): Tuple containing all processing parameters
    """
    (file_path, input_dir, output_dir, drugbank, vocabulary,
     disease_terms, data_dir, scripts_dir, metrics) = args

    try:
        # Calculate relative path to maintain directory structure
        relative_path = os.path.relpath(file_path, input_dir)
        output_path = os.path.join(output_dir, relative_path)
        output_dir_for_file = os.path.dirname(output_path)

        print(f"Processing file: {file_path}, Output directory: {output_dir_for_file}")
        process_drug_file(
            file_path,
            output_dir_for_file,
            drugbank,
            vocabulary,
            disease_terms,
            data_dir,
            scripts_dir,
            metrics
        )
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        if metrics:
            metrics.record_failure(file_path, e)

# ---------------------------------------------------------------------------------------- #
# Ontology Setup Functions
# ---------------------------------------------------------------------------------------- #

def setup_ontologies(ner: StandaloneBioNER, active_lexicons: List[str],
                     update: bool = False, metrics=None):
    """
    Setup required ontologies using standalone NER.

    Args:
        ner (StandaloneBioNER): NER instance
        active_lexicons (list): List of ontology names to setup
        update (bool): Whether to update/reprocess ontologies
        metrics (NERMetrics, optional): Collector for download times and results
    """
    # Pinned releases, so that every run uses the same ontology versions
    hpo = {
        'url': 'http://purl.obolibrary.org/obo/hp/releases/2025-05-06/hp.owl',
        'name': 'hpo',
        'type': 'owl',
        'description': 'Human Phenotype Ontology (2025-05-06)'
    }
    ontology_configs = {
        'doid': {
            'url': 'http://purl.obolibrary.org/obo/doid/releases/2025-05-30/doid.owl',
            'name': 'doid',
            'type': 'owl',
            'description': 'Disease Ontology (2025-05-30)'
        },
        'chebi': {
            'url': 'http://purl.obolibrary.org/obo/chebi/244/chebi.owl',
            'name': 'chebi',
            'type': 'owl',
            'description': 'ChEBI - Chemical Entities (release 244)'
        },
        'hp': hpo,
        'hpo': hpo,   # alias for hp
        'ordo': {
            'url': 'https://www.orphadata.com/data/ontologies/ordo/last_version/ORDO_en_4.7.owl',
            'name': 'ordo',
            'type': 'owl',
            'description': 'Orphanet Rare Disease Ontology (4.7)'
        },
    }

    print("\n" + "=" * 60)
    print("Setting up ontologies...")
    print("=" * 60)

    done = set()
    for lexicon in active_lexicons:
        lexicon_lower = lexicon.lower().strip()
        if not lexicon_lower:
            continue   # e.g. a trailing comma in the ini

        if lexicon_lower not in ontology_configs:
            print(f"WARNING: Unknown ontology '{lexicon}', skipping")
            continue

        config = ontology_configs[lexicon_lower]
        if config['name'] in done:   # 'hp' and 'hpo' are the same ontology
            continue
        done.add(config['name'])

        print(f"\n--- Processing {lexicon.upper()} ---")
        start = time.time()

        if update:
            print(f"Updating {lexicon}...")
            # Remove and re-add
            ner.remove_ontology(config['name'], delete_source=True)

        # Add ontology
        result = ner.add_ontology(
            url=config['url'],
            name=config['name'],
            ontology_type=config['type'],
            description=config['description'],
            skip_if_exists=not update
        )

        if metrics:
            metrics.record_ontology_download(config['name'], bool(result), time.time() - start)

        if result:
            print(f"{lexicon.upper()} ready")
        else:
            print(f"Failed to setup {lexicon.upper()}")

    print("\n" + "=" * 60)
    print("Ontology setup complete")
    print("=" * 60 + "\n")
# ---------------------------------------------------------------------------------------- #
# Main Function
# ---------------------------------------------------------------------------------------- #

def main(active_lexicon: List[str], 
         input_dir: str, 
         output_dir: str, 
         update: str, 
         drugbank_file: str,
         data_dir: str = './ontologies/data',
         scripts_dir: str = './ontologies/scripts',
         skip_ontology_setup=False,
         metrics_dir: str = None):
    """
    Main function to process drug data files in batch mode.
    
    Args:
        active_lexicon (list): List of ontologies to use
        input_dir (str): Directory containing input files
        output_dir (str): Directory to save output files
        update (str): Whether to update ontologies ('1' for yes)
        drugbank_file (str): Path to DrugBank CSV file
        data_dir (str): Directory containing ontology data
        scripts_dir (str): Directory containing shell scripts
        skip_ontology_setup: If True, skip ontology initialization (default: False)
        metrics_dir (str): Where to save the metrics report
            (default: a 'stats' folder next to output_dir)
    """
    # PHASE 1: Initialize Standalone NER
    logger = setup_logging()
    metrics = NERMetrics()
    
    # Initialize NER only if we need to setup ontologies
    if not skip_ontology_setup:
        logger.info("Initializing Standalone BioNER...")
        ner = StandaloneBioNER(
            data_dir=data_dir,
            scripts_dir=scripts_dir
        )
    
        # Check dependencies
        if not ner.check_dependencies():
            print("ERROR: Missing dependencies. Please install required tools.")
            sys.exit(1)
        
        if not ner.check_scripts():
            print("ERROR: Missing shell scripts. Please ensure they are in the scripts directory.")
            sys.exit(1)
        
        logger.info("\n" + "="*60)
        logger.info("Setting up ontologies...")
        logger.info("="*60)
        # PHASE 2: Setup ontologies
        should_update = (update == '1')
        setup_ontologies(ner, active_lexicon, update=should_update, metrics=metrics)
        
        logger.info("\n" + "="*60)
        logger.info("Ontology setup complete")
        logger.info("="*60)
    
    else:
        logger.info("Skipping ontology setup - using existing ontologies from previous task")

    # Record the versions of the ontologies used in this run
    versions = metrics.record_ontology_versions(data_dir)
    print(f"Ontology versions recorded: {', '.join(versions) or 'none found'}")
 
    # PHASE 3: Build disease dictionary from ORDO
    print("Building disease dictionary from ORDO...")
    disease_terms = build_disease_dictionary_from_lexicon(data_dir, 'ordo')
    print(f"Disease dictionary built with {len(disease_terms)} terms")

    # PHASE 4: Load DrugBank data
    print("Loading DrugBank data...")
    try:
        drugbank = load_drugbank_data(drugbank_file)
        vocabulary = create_vocabulary(drugbank)
        print(f"DrugBank loaded with {len(vocabulary)} drug names")
        metrics.metrics['drugbank'] = {
            'file': os.path.basename(drugbank_file),
            'drug_names': len(vocabulary),
        }
    except Exception as e:
        print(f"ERROR loading DrugBank: {e}")
        sys.exit(1)

    # PHASE 5: Find all JSON files to process
    print(f"\nScanning for JSON files in {input_dir}...")
    files_to_process = []
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith('.json'):
                input_file = os.path.join(root, filename)
                print(f"Adding file to process: {input_file}")
                files_to_process.append((
                    input_file, input_dir, output_dir, drugbank, 
                    vocabulary, disease_terms, data_dir, scripts_dir, metrics
                ))

    print(f"\nTotal files to process: {len(files_to_process)}")

    # PHASE 6: Process files in parallel using ThreadPoolExecutor
    if files_to_process:
        print("\nStarting parallel processing...")
        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.map(process_file_in_batch, files_to_process)
        print("\nAll files processed!")
    else:
        print("No JSON files found to process")

    # PHASE 7: Save the metrics report (one file per run, not overwritten)
    if metrics_dir is None:
        metrics_dir = os.path.join(os.path.dirname(os.path.normpath(output_dir)), 'stats')
    report_path = os.path.join(metrics_dir, f"ner_metrics_{time.strftime('%Y%m%d_%H%M%S')}.json")
    report = metrics.save_report(report_path)
    s = report['summary']
    print(f"\nMetrics saved to {report_path}")
    print(f"  Files: {s['total_files_processed']} processed, {s['total_files_failed']} failed "
          f"(of {len(files_to_process)})")
    print(f"  Distinct drugs: {s['distinct_drugs']}, distinct diseases: {s['distinct_diseases']}")
    print(f"  Indication pairs: {s['drug_disease_indications']}, "
          f"contraindication pairs: {s['drug_disease_contraindications']}")
    
    


if __name__ == '__main__':
    # Load configuration
    config = configparser.ConfigParser()
    config_file = 'bioner.ini'
    
    if not os.path.exists(config_file):
        print(f"ERROR: Configuration file '{config_file}' not found")
        sys.exit(1)
    
    config.read(config_file)
    
    # Extract configuration
    active_lexicons = [x.strip() for x in config.get('ONTO', 'active_lexicons').split(',')]
    update = config.get('ONTO', 'update', fallback='0')
    
    input_dir = config.get('PATH', 'input_json_dir')
    output_dir = config.get('PATH', 'preprocessing_output_dir')
    data_dir = config.get('STANDALONE_NER', 'data_dir')
    scripts_dir = config.get('STANDALONE_NER', 'scripts_dir')
    drugbank_file = config.get('PATH', 'drugbank_file', 
                               fallback='/opt/airflow/dags/NER/data/drugbank_vocabulary.csv')
    
    print("\n" + "="*60)
    print("Named Entities Batch Processing (Standalone NER)")
    print("="*60)
    print(f"Active lexicons: {', '.join(active_lexicons)}")
    print(f"Update mode: {'Yes' if update == '1' else 'No'}")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"DrugBank file: {drugbank_file}")
    print(f"Data directory: {data_dir}")
    print(f"Scripts directory: {scripts_dir}")
    print("="*60 + "\n")
    
    # Run main processing
    main(
        active_lexicon=active_lexicons,
        input_dir=input_dir,
        output_dir=output_dir,
        update=update,
        drugbank_file=drugbank_file,
        data_dir=data_dir,
        scripts_dir=scripts_dir
    )