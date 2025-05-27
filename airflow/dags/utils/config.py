# ------------------------------------------------------------------------------------------------------
# Objective:
# This class provides centralized configuration management for an Airflow DAG pipeline that processes pharmaceutical 
# data. It handles:
# 1. Loading and consolidating multiple INI configuration files from different system components
# 2. Configuring paths for download, extraction, and processing directories
# 3. Setting up input/output folder structures for the data pipeline
# 4. Managing Named Entity Recognition (NER) configuration parameters
# 5. Organizing vocabulary resources and database connection settings
# The purpose is to provide a single access point for all configuration parameters needed by the pipeline,
# making the DAG code cleaner and more maintainable.
# ------------------------------------------------------------------------------------------------------
import os
import configparser

def load_ini_config(path):
    """
    Loads and parses an INI configuration file.
    
    Args:
        path (str): Path to the INI file
        
    Returns:
        configparser.ConfigParser: Parsed configuration object
    """
    config = configparser.ConfigParser()
    config.read(path)
    return config

class DAGConfig:
    def __init__(self):
        # Carrega os arquivos de configuração necessários
        self.config_neo4j = load_ini_config('/opt/airflow/dags/database/neo4j.ini')     # Neo4j database settings
        self.config_upload = load_ini_config('/opt/airflow/dags/upload/upload.ini')     # File upload settings
        self.config_main = load_ini_config('/opt/airflow/dags/jsonify/config.ini')      # Main pipeline settings
        self.config_ner = load_ini_config('/opt/airflow/dags/NER/src/config.ini')       # NER component settings

        # Parse download configuration for each data source
        self.selected_directories = [i.strip("'").strip(" ") for i in self.config_upload['general']['selected_url'].split(",")]
        self.zip_urls = [self.config_upload['urls'][d] for d in self.selected_directories]
        self.zip_filenames = [os.path.basename(url) for url in self.zip_urls]
        self.zip_filepaths = [os.path.expanduser(f"{self.config_upload['general']['downloads_dir']}/{name}") 
                             for name in self.zip_filenames]
        self.src_directories = [os.path.expanduser(f"{self.config_upload['general']['downloads_dir']}/{os.path.splitext(name)[0]}/prescription") 
                               for name in self.zip_filenames]
        self.dest_directories = [os.path.expanduser(self.config_upload['dest_directory'][d]) 
                                for d in self.selected_directories]

        self.input_folders = [
            os.path.join(self.config_main['folders']['base_output_folder'], 'xml_results'),
            os.path.join(self.config_main['folders']['base_output_folder'], 'csv_results'),
            os.path.join(self.config_main['folders']['base_output_folder'], 'txt_results')
        ]
        self.output_folder = self.config_ner['PATH']['path_to_entities_json']
        self.output_folders = [
            os.path.join(self.output_folder, 'xml_results'),
            os.path.join(self.output_folder, 'csv_results'),
            os.path.join(self.output_folder, 'txt_results')
        ]
        self.input_json_dir = self.config_ner['PATH']['input_json_dir']
        self.preprocessing_output_dir = self.config_ner['PATH']['preprocessing_output_dir']
        self.active_lexicon = self.config_ner['ONTO']['active_lexicons'].replace(' ', '').split(',')
        self.update = self.config_ner['ONTO'].get('update')
        self.drugbank_file = os.path.join(self.config_ner['VOCABULARY']['output_folder'], 'drugbank vocabulary.csv')
        self.vocabulary_zip_url = self.config_ner['VOCABULARY']['zip_url']
        self.vocabulary_output_folder = self.config_ner['VOCABULARY']['output_folder']