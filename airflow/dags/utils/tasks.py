###############################################################################
#                                                                             #  
# @file: tasks.py                                                             #  
# @description: Task functions for Airflow DAG workflow                       #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This module contains all task functions that are called by Airflow DAGs.    #
# It implements the complete data processing pipeline from downloading data   #
# from external sources to processing, NER extraction, and Neo4j database     #
# loading. Each function represents a distinct task in the workflow.          #
#                                                                             #  
###############################################################################

import os
import sys
import json
import shutil
import logging
from utils.config import DAGConfig
from NER.Biomedical_preprocessing import BiomedicalPreprocessor
from NER.standalone_bioner import StandaloneBioNER
from NER.logging_config import setup_logging
from airflow.models.variable import Variable

# OBJECTIVE: Initialize configuration
# Load all configuration parameters for the DAG tasks
config = DAGConfig()

# -------------------------------------------------------------------------------------------
# AIRFLOW VARIABLE INITIALIZATION
# -------------------------------------------------------------------------------------------

def initialize_airflow_variables(**kwargs):
    """
    Initialize Airflow variables from configuration.
    
    Sets up notification emails and other Airflow variables needed across DAGs.
    """
    config = DAGConfig()
    
    # Set notification email from config
    email = config.config_ner.get('user', 'email', fallback='admin@example.com')
    Variable.set(key="notification_email", value=email)
    logging.info(f"Set notification_email to: {email}")


# -------------------------------------------------------------------------------------------
# DATA ACCESS TASKS
# -------------------------------------------------------------------------------------------

def download_zip_task(**kwargs):
    """
    Download ZIP files from configured URLs.
    
    This task downloads data files from the source URLs specified in the 
    configuration and saves them to the designated file paths.
    """
    from upload.download_from_url import download_file_from_url
    
    # OBJECTIVE: Download each ZIP file from its source URL
    for zip_url, zip_filepath in zip(config.zip_urls, config.zip_filepaths):
        logging.info(f"Starting download: {zip_url}")
        try:
            # Download the file and save it to the specified path
            download_file_from_url(zip_url, zip_filepath)
            logging.info(f"Downloaded: {zip_filepath}")
        except Exception as e:
            # Log error and propagate exception to mark task as failed
            logging.error(f"Download failed: {e}")
            raise


def unzip_task(**kwargs):
    """
    Extract all downloaded ZIP files.
    
    This task extracts the contents of all downloaded ZIP files,
    including any nested ZIP files within them.
    """
    from upload.unzip_directories import unzip_all_in_directory
    
    # OBJECTIVE: Extract all ZIP files to their respective directories
    for zip_filepath in config.zip_filepaths:
        unzip_all_in_directory(zip_filepath)


def extract_xml_files_task(**kwargs):
    """
    Extract and copy files from source to destination directories based on file patterns.
    
    This task copies relevant files (XML, CSV, TXT) from their source directories
    to the appropriate destination directories for further processing.
    """
    from upload.extract_files import copy_files, get_previous_month_csv_pattern
    from upload.upload_loader import UploadLoader
    
    # OBJECTIVE: Initialize configuration
    config = UploadLoader()
    downloads_dir = config.get_downloads_dir()
    selected_directories = config.get_selected_directories()
    dest_directories = config.get_dest_directories()
    source_paths = config.get_source_paths()
    file_patterns = config.get_file_patterns()
    
    # OBJECTIVE: Create destination directories if they don't exist
    for dest in dest_directories:
        os.makedirs(dest, exist_ok=True)
        logging.info(f"Ensured directory exists: {dest}")
    
    # OBJECTIVE: Read the list of files to process
    filename_file = os.path.join(downloads_dir, 'filename.txt')
    if not os.path.exists(filename_file):
        logging.error(f"filename.txt not found at {filename_file}")
        raise FileNotFoundError(f"filename.txt not found at {filename_file}")
    
    with open(filename_file, 'r') as f:
        file_filenames = [line.strip() for line in f.readlines()]
    
    logging.info(f"Processing {len(file_filenames)} file(s) from filename.txt")
    
    # OBJECTIVE: Process each file according to its source type
    for i, filename in enumerate(file_filenames):
        # Determine source type based on filename pattern
        if 'purplebook' in filename.lower():
            source_type = 'purplebook'
            idx = selected_directories.index('purplebook')
        elif 'orangebook' in filename.lower():
            source_type = 'orangebook'
            idx = selected_directories.index('orangebook')
        elif 'dm_spl' in filename.lower() or 'dailymed' in filename.lower():
            source_type = 'dailymed'
            idx = selected_directories.index('dailymed')
        else:
            logging.warning(f"Unknown file type: {filename}, skipping...")
            continue
        
        logging.info(f"[{i+1}/{len(file_filenames)}] Processing {source_type}: {filename}")
        
        base_dir = os.path.splitext(filename)[0]
        
        # Handle different source types
        if source_type == "purplebook":
            src_file = os.path.join(downloads_dir, get_previous_month_csv_pattern())
            dest_directory = dest_directories[idx]
            if os.path.exists(src_file):
                shutil.copy(src_file, dest_directory)
                logging.info(f"Copied {src_file} to {dest_directory}")
            else:
                logging.warning(f"File not found: {src_file}")
        
        elif source_type == 'orangebook':
            # For orangebook: extracted structure is orangebook/orangebook/products.txt
            src_directory = os.path.join(downloads_dir, base_dir, source_paths[idx])
            src_file = os.path.join(src_directory, file_patterns[idx])
            dest_directory = dest_directories[idx]
            
            if os.path.exists(src_file):
                shutil.copy(src_file, dest_directory)
                logging.info(f"Copied {src_file} to {dest_directory}")
            else:
                logging.warning(f"File not found: {src_file}")
        
        elif source_type == 'dailymed':
            # For dailymed: structure is dm_spl_monthly_update_XXX/prescription/*.xml
            if source_paths[idx] == '.':
                src_directory = os.path.join(downloads_dir, base_dir)
            else:
                src_directory = os.path.join(downloads_dir, base_dir, source_paths[idx])
            
            logging.info(f"Source directory: {src_directory}")
            logging.info(f"File pattern: {file_patterns[idx]}")
            
            if not os.path.exists(src_directory):
                logging.warning(f"Source directory does not exist: {src_directory}")
                continue
            
            # Copy files using the configured pattern (*.xml from prescription folder only)
            logging.info(f"Copying {file_patterns[idx]} files from {src_directory} to {dest_directories[idx]}")
            copy_files(src_directory, dest_directories[idx], file_patterns[idx])
    
    logging.info("File extraction complete")


# -------------------------------------------------------------------------------------------
# CONVERSION TASKS
# -------------------------------------------------------------------------------------------

def convert_files_to_json_task(**kwargs):
    """
    Convert XML, CSV e TXT files to JSON format.
    """
    # OBJECTIVE: Execute the main conversion process
    from jsonify.conversion import convert_all_files
    convert_all_files()


# -------------------------------------------------------------------------------------------
# NER SETUP TASKS
# -------------------------------------------------------------------------------------------

def setup_ontologies_task(**kwargs):
    """
    Task: Setup and download ontologies for Named Entity Recognition.
    
    This task initializes the BioNER system, checks dependencies, and downloads/processes
    all active ontologies (DOID, ChEBI, HPO, ORDO, etc.) as specified in configuration.
    """
    logging.info("Setting up ontologies...")
    logger = setup_logging()
    logger.info("Setting up ontologies...")
    
    # Load configuration
    config = DAGConfig()
    
    # Initialize NER
    ner = StandaloneBioNER(
        data_dir=config.ontology_data_dir,
        scripts_dir=config.ontology_scripts_dir
    )
    
    # Check dependencies
    if not ner.check_dependencies():
        raise Exception("Missing system dependencies for NER")
    
    if not ner.check_scripts():
        raise Exception("Missing shell scripts for NER")
    
    # Get active ontologies from configuration
    active_ontologies = config.get_active_ontologies()
    logging.info(f"Active ontologies: {active_ontologies}")
    
    # Setup each ontology
    for onto_name in active_ontologies:
        # Get ontology configuration
        onto_config = config.get_ontology_config(onto_name)
        
        if not onto_config:
            logging.warning(f"Configuration not found for {onto_name}")
            continue
        
        logging.info(f"\nSetting up {onto_name}...")
        logging.info(f"  Description: {onto_config['description']}")
        logging.info(f"  URL: {onto_config['url']}")
        
        # Add ontology (skip if already exists and update flag is not set)
        result = ner.add_ontology(
            url=onto_config['url'],
            name=onto_config['name'],
            description=onto_config['description'],
            skip_if_exists=(config.update != '1')
        )
        
        if result:
            logging.info(f"{onto_name} ready")
        else:
            logging.warning(f"Failed to setup {onto_name}")
    
    # Show configured ontologies
    ner.show_ontologies()
    
    logging.info("\nOntology setup complete")


def download_vocabulary_task(vocabulary_name='drugbank', **kwargs):
    """
    Download vocabulary files for NER processing.
    
    Args:
        vocabulary_name: Name of vocabulary to download ('drugbank', 'orphanet', etc.)
    """
    from NER.download_vocabulary import download_and_extract_zip
    
    config = DAGConfig()
    
    vocab_config = {
        'drugbank': {
            'url': config.vocabulary_drugbank_url,
            'output_folder': config.vocabulary_output_folder,
            'file_path': config.drugbank_file
        },
        # Add more vocabularies as needed
    }

    if vocabulary_name not in vocab_config:
        raise ValueError(f"Unknown vocabulary: {vocabulary_name}")
    
    vocab = vocab_config[vocabulary_name]

    # Check if file exists
    if os.path.exists(vocab['file_path']):
        logging.info(f"{vocabulary_name} already exists at: {vocab['file_path']}")
        return vocab['file_path']
    
    # Download
    try:
        result = download_and_extract_zip(
            url=vocab['url'],
            output_folder=vocab['output_folder']
        )
        logging.info(f"{vocabulary_name} downloaded to: {result}")
        return result
    except Exception as e:
        logging.error(f"Failed to download {vocabulary_name}: {e}")
        raise


# -------------------------------------------------------------------------------------------
# DATA PREPROCESSING TASKS
# -------------------------------------------------------------------------------------------

def preprocess_json_task(**kwargs):
    """
    Preprocess JSON files for NER processing.
    
    This task applies biomedical text preprocessing to the JSON files, preparing
    specific fields for Named Entity Recognition (NER) processing.
    """
    logging.info("Preprocessing text...")
    
    config = DAGConfig()
    
    # Initialize preprocessor with biomedical-specific settings
    preprocessor = BiomedicalPreprocessor(
        preserve_case=False,
        keep_punctuation=True,
        remove_stops=True
    )
    
    # Define input/output directories
    input_dir = config.input_json_dir 
    output_dir = config.preprocessing_output_dir
    
    # Fields to process - can be customized per use case
    fields_to_process = [
        'ingredients', 
        'indications', 
        'contraindications', 
        'warningsAndPrecautions', 
        'adverseReactions',
        'description'  # Added based on ner_dag.py example
    ]
    
    logging.info(f"Input directory: {input_dir}")
    logging.info(f"Output directory: {output_dir}")
    logging.info(f"Fields to process: {fields_to_process}")

    # OBJECTIVE: Process all JSON files while preserving directory structure
    for root, dirs, files in os.walk(input_dir):
        # Maintain the same directory structure in the output
        relative_path = os.path.relpath(root, input_dir)
        output_subdir = os.path.join(output_dir, relative_path)
        os.makedirs(output_subdir, exist_ok=True)

        # Process each JSON file in the current directory
        for file in files:
            if file.endswith(".json"):
                input_file = os.path.join(root, file)
                output_file = os.path.join(output_subdir, file)
                # Apply preprocessing to the specified fields
                preprocessor.preprocess_json_file(
                    input_file, 
                    output_file, 
                    fields_to_process=fields_to_process
                )
    
    logging.info("\nText preprocessing complete")


# -------------------------------------------------------------------------------------------
# NER PROCESSING TASKS
# -------------------------------------------------------------------------------------------

def ner_process_task(**kwargs):
    """
    Perform Named Entity Recognition (NER) on preprocessed JSON files.
    
    This task identifies and extracts biomedical entities (drugs, diseases, chemicals, etc.)
    from the preprocessed text fields in the JSON files using the configured ontologies.
    """
    from NER.ner_entities_batch import main as batch_process
    
    logging.info("Starting NER entity extraction...")
    
    config = DAGConfig()
    
    # Define input/output directories
    input_dir = config.preprocessing_output_dir  
    output_dir = config.output_folder

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    logging.info(f"Input folder: {input_dir}")
    logging.info(f"Output folder: {output_dir}")
    logging.info(f"Active lexicons: {config.active_lexicon}")
    logging.info(f"Update mode: {config.update}")
    logging.info(f"Skipping ontology setup (already done in setup_ontologies task)")


    try:
        # Execute main NER processing function with configured parameters
        batch_process(
            active_lexicon=config.active_lexicon,
            input_dir=input_dir,
            output_dir=output_dir,
            update=config.update,
            drugbank_file=config.drugbank_file,
            data_dir=config.ontology_data_dir,
            scripts_dir=config.ontology_scripts_dir,
            skip_ontology_setup=True  # Add this parameter
        )
        logging.info(f"NER processing completed successfully. Results saved in {output_dir}")
    except Exception as e:
        logging.error(f"Error during NER processing: {str(e)}")
        raise


# -------------------------------------------------------------------------------------------
# VALIDATION TASKS
# -------------------------------------------------------------------------------------------

def validate_results_task(**kwargs):
    """
    Validate NER extraction results.
    
    This task checks that the NER processing completed successfully by verifying:
    - Output directories exist
    - Files were processed
    - Entities were extracted and added to the JSON files
    """
    logging.info("Validating NER results...")
    
    config = DAGConfig()
    
    # Check output directories
    for output_dir in config.output_folders:
        if not os.path.exists(output_dir):
            raise Exception(f"Output directory not found: {output_dir}")
        
        # Count processed files
        json_files = [f for f in os.listdir(output_dir) if f.endswith('.json')]
        logging.info(f"\n{output_dir}:")
        logging.info(f"  Files processed: {len(json_files)}")
        
        # Sample validation - check first file has entities
        if json_files:
            sample_file = os.path.join(output_dir, json_files[0])
            with open(sample_file, 'r') as f:
                data = json.load(f)
            
            # Check if entities were added
            data_str = str(data)
            has_drugbank = 'drugbank_id' in data_str
            has_chebi = 'chebi_id' in data_str
            has_doid = 'doid_entities' in data_str
            
            logging.info(f"  Sample file: {json_files[0]}")
            logging.info(f"    DrugBank IDs: {'✓' if has_drugbank else '✗'}")
            logging.info(f"    ChEBI IDs: {'✓' if has_chebi else '✗'}")
            logging.info(f"    DOID entities: {'✓' if has_doid else '✗'}")
        else:
            logging.warning(f"  No JSON files found in {output_dir}")
    
    logging.info("\nValidation complete")


# -------------------------------------------------------------------------------------------
# DATABASE LOADING TASKS
# -------------------------------------------------------------------------------------------

def send_to_neo4j_task(**kwargs):
    """
    Send processed data to Neo4j graph database.
    
    This task loads the processed and extracted entities into a Neo4j graph database,
    creating the knowledge graph for further analysis and querying.
    """
    from database.knowledge_graph import process_xml_file, Neo4jHandler
    
    # OBJECTIVE: Initialize Neo4j connection
    logging.info("Starting the task of sending to Neo4j")
    neo4j_handler = Neo4jHandler(
        uri=config.config_neo4j['neo4j']['uri'],
        user=config.config_neo4j['neo4j']['user'],
        password=config.config_neo4j['neo4j']['password']
    )
    
    # OBJECTIVE: Define folders containing processed data to be loaded
    folders = [
        os.path.join(config.output_folder, 'xml_files'),
        os.path.join(config.output_folder, 'csv_files'),
        os.path.join(config.output_folder, 'txt_files')
    ]
    
    # OBJECTIVE: Process each folder and load JSON files to Neo4j
    for folder in folders:
        logging.info(f"Checking the existence of the folder: {folder}")
        
        if os.path.exists(folder):
            logging.info(f"Processing folder: {folder}")
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                logging.info(f"Checking the file: {file_path}")
                # Process only JSON files
                if os.path.isfile(file_path) and file_path.endswith('.json'):
                    logging.info(f"Processing file: {file_path}")
                    process_xml_file(file_path, neo4j_handler)
                else:
                    logging.info(f"File ignored: {file_path}")
        else:
            logging.warning(f"Folder not found: {folder}")
    
    logging.info("Task of sending to Neo4j completed")


# -------------------------------------------------------------------------------------------
# GRAPH EXPORT TASKS
# -------------------------------------------------------------------------------------------

def export_graph_task(**kwargs):
    """
    Export drug-disease relationships from Neo4j to CSV files.

    Produces two files in the configured output directory:
      - indicated.csv        : Drug -[TREATS]-> Disease
      - contraindicated.csv  : Drug -[CONTRAINDICATED_FOR]-> Disease
    """
    from database.graph_export import export_graph_to_csv

    logging.info("Starting graph export to CSV...")

    config = DAGConfig()

    output_dir = os.path.join(
        config.config_neo4j.get('neo4j', 'export_dir',
                                fallback='/opt/airflow/dags/database/output')
    )

    results = export_graph_to_csv(
        uri=config.config_neo4j['neo4j']['uri'],
        user=config.config_neo4j['neo4j']['user'],
        password=config.config_neo4j['neo4j']['password'],
        output_dir=output_dir,
    )

    for name, info in results.items():
        logging.info(f"  {name}: {info['rows']} rows -> {info['path']}")

    logging.info("Graph export complete")

