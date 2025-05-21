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
import logging
import configparser
from utils.config import DAGConfig
from NER.Biomedical_preprocessing import BiomedicalPreprocessor

# OBJECTIVE: Initialize configuration
# Load all configuration parameters for the DAG tasks
config = DAGConfig()

# -------------------------------------------------------------------------------------------
# DATA ACQUISITION TASKS
# -------------------------------------------------------------------------------------------

def download_zip_task():
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

def unzip_task():
    """
    Extract all downloaded ZIP files.
    
    This task extracts the contents of all downloaded ZIP files,
    including any nested ZIP files within them.
    """
    from upload.unzip_directories import unzip_all_in_directory
    
    # OBJECTIVE: Extract all ZIP files to their respective directories
    for zip_filepath in config.zip_filepaths:
        unzip_all_in_directory(zip_filepath)

def extract_xml_files_task():
    """
    Extract and copy XML files from source to destination directories.
    
    This task copies relevant XML files from their source directories
    to the appropriate destination directories for further processing.
    """
    from upload.extract_files import copy_xml_files
    
    # OBJECTIVE: Copy XML files from each source to its corresponding destination
    for src, dest in zip(config.src_directories, config.dest_directories):
        copy_xml_files(src, dest)

def convert_files_to_json_task():
    """
    Convert XML files to JSON format.
    
    This task processes all extracted XML files and converts them to JSON format
    for easier data manipulation in subsequent steps.
    """
    # OBJECTIVE: Execute the main conversion process
    from jsonify.src import main
    main.main()

# -------------------------------------------------------------------------------------------
# DATA PROCESSING TASKS
# -------------------------------------------------------------------------------------------

def download_vocabulary_task():
    """
    Download and extract vocabulary files for NER processing.
    
    This task downloads terminology vocabularies and ontologies needed for
    Named Entity Recognition (NER) processing.
    """
    # OBJECTIVE: Download and extract vocabulary ZIP file
    from NER.download_vocabulary import download_and_extract_zip
    download_and_extract_zip(config.vocabulary_zip_url, config.vocabulary_output_folder)

def preprocess_json_task():
    """
    Preprocess JSON files for NER processing.
    
    This task applies biomedical text preprocessing to the JSON files, preparing
    specific fields for Named Entity Recognition (NER) processing.
    """
    # OBJECTIVE: Initialize the biomedical preprocessor
    preprocessor = BiomedicalPreprocessor()
    
    # Define input/output directories and fields to process
    input_dir = config.input_json_dir 
    output_dir = config.preprocessing_output_dir  
    fields_to_process = ["ingredients", "indications", "contraindications", 
                         "warningsAndPrecautions", "adverseReactions"]

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
                preprocessor.preprocess_json_file(input_file, output_file, fields_to_process=fields_to_process)

def ner_process_task():
    """
    Perform Named Entity Recognition (NER) on preprocessed JSON files.
    
    This task identifies and extracts biomedical entities (drugs, diseases, etc.)
    from the preprocessed text fields in the JSON files.
    """
    from NER.src.mer_entities_batch import main

    # Define input/output directories
    input_folder = config.preprocessing_output_dir  
    output_folder = config.output_folder 

    # Ensure output directory exists
    os.makedirs(output_folder, exist_ok=True)

    # OBJECTIVE: Process files with NER to extract entities
    logging.info(f"Starting NER processing for files in {input_folder}")
    logging.info(f"Output folder: {output_folder}")

    try:
        # Execute main NER processing function with configured parameters
        main(config.active_lexicon, input_folder, output_folder, config.update, config.drugbank_file)
        logging.info(f"NER processing completed successfully for {input_folder}. Results saved in {output_folder}")
    except Exception as e:
        logging.error(f"Error during NER processing for {input_folder}: {str(e)}")

# -------------------------------------------------------------------------------------------
# DATABASE LOADING TASKS
# -------------------------------------------------------------------------------------------

def send_to_neo4j_task():
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
        os.path.join(config.output_folder, 'xml_results'),
        os.path.join(config.output_folder, 'csv_results'),
        os.path.join(config.output_folder, 'txt_results')
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