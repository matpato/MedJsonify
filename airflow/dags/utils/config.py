import os
import configparser
from jsonify.src.config_loader import ConfigLoader

def load_ini_config(path):
    config = configparser.ConfigParser()
    config.read(path)
    return config

class DAGConfig:
    def __init__(self):
        self.config_loader = ConfigLoader()
        self.config_neo4j = load_ini_config('/opt/airflow/dags/database/neo4j.ini')
        self.config_upload = load_ini_config('/opt/airflow/dags/upload/upload.ini')
        self.config_main = load_ini_config('/opt/airflow/dags/jsonify/config.ini')
        self.config_ner = load_ini_config('/opt/airflow/dags/NER/src/config.ini')

        self.file_types = self.config_loader.get_file_types()
        self.base_output_folder = self.config_loader.get_base_output_folder()
        
        self.selected_directories = [i.strip("'").strip(" ") for i in self.config_upload['general']['selected_url'].split(",")]

        self.zip_urls = [self.config_upload['urls'][d] for d in self.selected_directories]
        self.zip_filenames = [os.path.basename(url) for url in self.zip_urls]
        self.zip_filepaths = [os.path.expanduser(f"{self.config_upload['general']['downloads_dir']}/{name}") for name in self.zip_filenames]
        
        self.src_directories = [os.path.expanduser(f"{self.config_upload['general']['downloads_dir']}/{os.path.splitext(name)[0]}/prescription") for name in self.zip_filenames]
        self.dest_directories = [os.path.expanduser(self.config_upload['dest_directory'][d]) for d in self.selected_directories]     

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

        self.active_lexicon = self.config_ner['ONTO']['active_lexicons'].replace(' ', '').split(',')
        self.update = self.config_ner['ONTO'].get('update')
        self.drugbank_file = os.path.join(self.config_ner['VOCABULARY']['output_folder'], 'drugbank vocabulary.csv')

        self.vocabulary_zip_url = self.config_ner['VOCABULARY']['zip_url']
        self.vocabulary_output_folder = self.config_ner['VOCABULARY']['output_folder']