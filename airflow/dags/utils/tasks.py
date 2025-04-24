import os
import logging
import configparser
from utils.config import DAGConfig

config = DAGConfig()

# -------------------------------------------------------------------------------------------

def download_zip_task():
    from upload.download_from_url import download_file_from_url
    for zip_url, zip_filepath in zip(config.zip_urls, config.zip_filepaths):
        logging.info(f"Starting download: {zip_url}")
        try:
            download_file_from_url(zip_url, zip_filepath)
            logging.info(f"Downloaded: {zip_filepath}")
        except Exception as e:
            logging.error(f"Download failed: {e}")
            raise

# -------------------------------------------------------------------------------------------

def unzip_task():
    from upload.unzip_directories import unzip_all_in_directory
    for zip_filepath in config.zip_filepaths:
        unzip_all_in_directory(zip_filepath)

# -------------------------------------------------------------------------------------------

def extract_xml_files_task():
    from upload.extract_files import copy_xml_files
    for src, dest in zip(config.src_directories, config.dest_directories):
        copy_xml_files(src, dest)

# -------------------------------------------------------------------------------------------   

def convert_files_to_json_task():
    from jsonify.src import main
    main.main()

# -------------------------------------------------------------------------------------------

def send_to_neo4j_task():
    from database.knowledge_graph import process_xml_file, Neo4jHandler
    logging.info("Starting the task of sending to Neo4j")
    neo4j_handler = Neo4jHandler(
        uri=config.config_neo4j['neo4j']['uri'],
        user=config.config_neo4j['neo4j']['user'],
        password=config.config_neo4j['neo4j']['password']
    )
    
    folders = [
        os.path.join(config.output_folder, 'xml_results'),
        os.path.join(config.output_folder, 'csv_results') 
    ]
    
    for folder in folders:
        logging.info(f"Checking the existence of the folder: {folder}")
        
        if os.path.exists(folder):
            logging.info(f"Processing folder: {folder}")
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                logging.info(f"Checking the file: {file_path}")
                if os.path.isfile(file_path) and file_path.endswith('.json'):
                    logging.info(f"Processing file: {file_path}")
                    process_xml_file(file_path, neo4j_handler)
                else:
                    logging.info(f"File ignored: {file_path}")
        else:
            logging.warning(f"Folder not found: {folder}")
    
    logging.info("Task of sending to Neo4j completed")
    
# -------------------------------------------------------------------------------------------

def download_vocabulary_task():
    from NER.download_vocabulary import download_and_extract_zip
    download_and_extract_zip(config.vocabulary_zip_url, config.vocabulary_output_folder)

# -------------------------------------------------------------------------------------------

def ner_process_task():
    import os
    import logging
    from NER.src.mer_entities_batch import main
    from utils.config import DAGConfig

    config = DAGConfig()

    for folder in config.output_folders:
        os.makedirs(folder, exist_ok=True)

    for input_folder, output_folder in zip(config.input_folders, config.output_folders):
        logging.info(f"Starting NER processing for files in {input_folder}")

        try:
            main(config.active_lexicon, input_folder, output_folder, config.update, config.drugbank_file)
            logging.info(f"NER processing completed successfully for {input_folder}. Results saved in {output_folder}")
        except Exception as e:
            logging.error(f"Error during NER processing for {input_folder}: {str(e)}")

# -------------------------------------------------------------------------------------------
