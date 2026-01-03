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
#
# USAGE:
#     from utils.config import DAGConfig
#     config = DAGConfig()
#     print(config.ontology_data_dir)
#     print(config.get_ontology_config('doid'))
#
# ------------------------------------------------------------------------------------------------------
import os
import configparser
from pathlib import Path
from typing import Dict, List, Optional
from functools import lru_cache

def load_ini_config(path) -> configparser.ConfigParser:
    """Load INI configuration file"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Configuration file not found: {path}")
    
    config = configparser.ConfigParser()
    config.read(path)
    return config

def ensure_directory(path: str) -> str:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path
        
    Returns:
        Absolute path to the directory
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(abs_path, exist_ok=True)
    return abs_path

class DAGConfig:

    BASE_DAG_DIR = '/opt/airflow/dags'
    
    UPLOAD_CONFIG_PATH = os.path.join(BASE_DAG_DIR, 'upload/upload.ini')
    JSONIFY_CONFIG_PATH = os.path.join(BASE_DAG_DIR, 'jsonify/jsonify.ini')
    NER_CONFIG_PATH = os.path.join(BASE_DAG_DIR, 'NER/bioner.ini')
    NEO4J_CONFIG_PATH = os.path.join(BASE_DAG_DIR, 'database/neo4j.ini')

    def __init__(self):

        # -------------------------------------------------------------------------------------------
        # LOAD CONFIGURATION FILES
        # -------------------------------------------------------------------------------------------
        # Load all configuration files
        self.config_upload = load_ini_config(self.UPLOAD_CONFIG_PATH)
        self.config_jsonify = load_ini_config(self.JSONIFY_CONFIG_PATH)
        self.config_ner = load_ini_config(self.NER_CONFIG_PATH)
        self.config_neo4j = load_ini_config(self.NEO4J_CONFIG_PATH)
        
        # Initialize configuration sections
        self._init_upload_config()
        self._init_conversion_config()
        self._init_ner_config()
        self._init_ontology_config()
        self._init_neo4j_config()

    # -------------------------------------------------------------------------------------------
    # UPLOAD/DATA ACQUISITION CONFIGURATION
    # -------------------------------------------------------------------------------------------
    
    def _init_upload_config(self):
        """Initialize data acquisition and upload configuration."""
        
        # Parse selected data sources
        self.selected_directories = [
            source.strip("'").strip()
            for source in self.config_upload['general']['selected_url'].split(',')
        ]
        
        # Download URLs and file paths
        self.zip_urls = [
            self.config_upload['urls'][source]
            for source in self.selected_directories
        ]
        
        self.zip_filenames = [
            os.path.basename(url)
            for url in self.zip_urls
        ]
        
        downloads_dir = self.config_upload['general']['downloads_dir']
        self.zip_filepaths = [
            os.path.expanduser(os.path.join(downloads_dir, filename))
            for filename in self.zip_filenames
        ]
        
        # Source directories (after extraction)
        self.src_directories = [
            os.path.expanduser(
                os.path.join(
                    downloads_dir,
                    os.path.splitext(filename)[0],
                    'prescription'
                )
            )
            for filename in self.zip_filenames
        ]
        
        # Destination directories for extracted files
        self.dest_directories = [
            os.path.expanduser(self.config_upload['dest_directory'][source])
            for source in self.selected_directories
        ]

    # -------------------------------------------------------------------------------------------
    # FILE CONVERSION CONFIGURATION
    # -------------------------------------------------------------------------------------------
    
    def _init_conversion_config(self):
        """Initialize file conversion configuration."""
        
        # Base output folder for conversion
        base_output = self.config_jsonify['folders']['base_output_folder']
        
        # Input folders for conversion (organized by file type)
        self.conversion_input_folders = [
            os.path.join(base_output, 'xml_files'),
            os.path.join(base_output, 'csv_files'),
            os.path.join(base_output, 'txt_files')
        ]
        
        # Maintain backward compatibility
        self.input_folders = self.conversion_input_folders

    # -------------------------------------------------------------------------------------------
    # NAMED ENTITY RECOGNITION (NER) CONFIGURATION
    # -------------------------------------------------------------------------------------------

    def _init_ner_config(self):
        """Initialize Named Entity Recognition configuration."""
        
        # Basic NER settings
        self.ner_sample_size = int(self.config_ner['SAMPLE']['splitedSize'])
        
        # Input/Output directories for NER pipeline
        self.ner_input_dir = self.config_ner['PATH']['input_json_dir']
        self.ner_preprocessing_output_dir = self.config_ner['PATH']['preprocessing_output_dir']
        self.ner_output_dir = self.config_ner['PATH']['path_to_entities_json']
        
        # Maintain backward compatibility with old names
        self.input_json_dir = self.ner_input_dir
        self.preprocessing_output_dir = self.ner_preprocessing_output_dir
        self.output_folder = self.ner_output_dir
        
        # Output folders organized by file type
        self.ner_output_folders = [
            os.path.join(self.ner_output_dir, 'xml_files'),
            os.path.join(self.ner_output_dir, 'csv_files'),
            os.path.join(self.ner_output_dir, 'txt_files')
        ]
        self.output_folders = self.ner_output_folders  # Backward compatibility
        
        # Active lexicons and update settings
        active_lexicons_str = self.config_ner['ONTO']['active_lexicons']
        self.active_lexicons = [
            lexicon.strip()
            for lexicon in active_lexicons_str.replace(' ', '').split(',')
        ]
        self.active_lexicon = self.active_lexicons  # Backward compatibility
        
        self.ontology_update_enabled = self.config_ner['ONTO'].get('update', '0') == '1'
        self.update = self.config_ner['ONTO'].get('update', '0')  # Backward compatibility
        
        # Vocabulary resources
        self.drugbank_url = self.config_ner['VOCABULARY']['drugbank_url']
        self.vocabulary_output_folder = self.config_ner['VOCABULARY']['output_folder']
        self.drugbank_file = self.config_ner['PATH']['drugbank_file']
        
        # Backward compatibility
        self.vocabulary_drugbank_url = self.drugbank_url
    
    # -------------------------------------------------------------------------------------------
    # ONTOLOGY CONFIGURATION
    # -------------------------------------------------------------------------------------------
    
    def _init_ontology_config(self):
        """
        Initialize ontology configuration.
        
        This method sets up the ontology directories and parses ontology
        configurations from the [STANDALONE_NER] and [ONTOLOGIES] sections
        of bioner.ini.
        """
        
        # Ontology directories - Single Source of Truth
        self.ontology_data_dir = self.config_ner.get(
            'STANDALONE_NER',
            'data_dir',
            fallback='/opt/airflow/dags/NER/ontologies/data'
        )
        
        self.ontology_scripts_dir = self.config_ner.get(
            'STANDALONE_NER',
            'scripts_dir',
            fallback='/opt/airflow/dags/NER/ontologies/scripts'
        )
        
        # Parse ontology configurations from [ONTOLOGIES] section
        self.ontologies = {}
        
        if 'ONTOLOGIES' in self.config_ner:
            # Extract unique ontology names
            ontology_names = set()
            for key in self.config_ner['ONTOLOGIES']:
                if '_' in key:
                    onto_name = key.split('_')[0]
                    ontology_names.add(onto_name)
            
            # Build configuration for each ontology
            for onto_name in ontology_names:
                self.ontologies[onto_name] = {
                    'url': self.config_ner.get(
                        'ONTOLOGIES',
                        f'{onto_name}_url',
                        fallback=''
                    ),
                    'name': self.config_ner.get(
                        'ONTOLOGIES',
                        f'{onto_name}_name',
                        fallback=onto_name
                    ),
                    'description': self.config_ner.get(
                        'ONTOLOGIES',
                        f'{onto_name}_description',
                        fallback=f'{onto_name.upper()} Ontology'
                    ),
                    'type': self.config_ner.get(
                        'ONTOLOGIES',
                        f'{onto_name}_type',
                        fallback='owl'
                    )
                }
    
    # -------------------------------------------------------------------------------------------
    # NEO4J DATABASE CONFIGURATION
    # -------------------------------------------------------------------------------------------
    
    def _init_neo4j_config(self):
        """Initialize Neo4j database configuration."""
        
        # Store the entire config for backward compatibility
        # Access as: config.config_neo4j['neo4j']['uri']
        pass  # config_neo4j is already loaded in __init__

    # -------------------------------------------------------------------------------------------
    # PUBLIC API - ONTOLOGY METHODS
    # -------------------------------------------------------------------------------------------
    
    def get_ontology_config(self, ontology_name: str) -> Optional[Dict[str, str]]:
        """
        Get configuration for a specific ontology.
        
        Args:
            ontology_name: Name of the ontology (e.g., 'doid', 'chebi', 'hpo', 'ordo')
            
        Returns:
            Dictionary with 'url', 'name', 'description', 'type' or None if not found
            
        Example:
            >>> config = DAGConfig()
            >>> doid = config.get_ontology_config('doid')
            >>> print(doid['url'])
            http://purl.obolibrary.org/obo/doid.owl
        """
        return self.ontologies.get(ontology_name.lower())
    
    def get_all_ontology_configs(self) -> Dict[str, Dict[str, str]]:
        """
        Get configuration for all ontologies.
        
        Returns:
            Dictionary mapping ontology names to their configurations
            
        Example:
            >>> config = DAGConfig()
            >>> for name, cfg in config.get_all_ontology_configs().items():
            ...     print(f"{name}: {cfg['description']}")
        """
        return self.ontologies.copy()
    
    def get_active_ontologies(self) -> List[str]:
        """
        Get list of active ontology names from configuration.
        
        Returns:
            List of active ontology names (e.g., ['doid', 'chebi', 'hpo', 'ordo'])
            
        Example:
            >>> config = DAGConfig()
            >>> print(config.get_active_ontologies())
            ['doid', 'chebi', 'hp', 'ordo']
        """
        return self.active_lexicons.copy()
    
    def is_ontology_active(self, ontology_name: str) -> bool:
        """
        Check if an ontology is currently active.
        
        Args:
            ontology_name: Name of the ontology to check
            
        Returns:
            True if the ontology is active, False otherwise
        """
        return ontology_name.lower() in [o.lower() for o in self.active_lexicons]
    

    # -------------------------------------------------------------------------------------------
    # PUBLIC API - NEO4J METHODS
    # -------------------------------------------------------------------------------------------
    
    def get_neo4j_uri(self) -> str:
        """Get Neo4j connection URI."""
        return self.config_neo4j.get('neo4j', 'uri', fallback='bolt://localhost:7687')
    
    def get_neo4j_user(self) -> str:
        """Get Neo4j username."""
        return self.config_neo4j.get('neo4j', 'user', fallback='neo4j')
    
    def get_neo4j_password(self) -> str:
        """Get Neo4j password."""
        return self.config_neo4j.get('neo4j', 'password', fallback='password')
    
    def get_neo4j_config(self) -> Dict[str, str]:
        """
        Get complete Neo4j configuration.
        
        Returns:
            Dictionary with 'uri', 'user', and 'password'
        """
        return {
            'uri': self.get_neo4j_uri(),
            'user': self.get_neo4j_user(),
            'password': self.get_neo4j_password()
        }

    # -------------------------------------------------------------------------------------------
    # PUBLIC API - PATH METHODS
    # -------------------------------------------------------------------------------------------
    
    def get_conversion_input_paths(self) -> List[str]:
        """
        Get all input paths for the conversion step.
        
        Returns:
            List of paths to directories containing files to convert
        """
        return self.conversion_input_folders.copy()
    
    def get_ner_input_path(self) -> str:
        """Get input directory for NER processing."""
        return self.ner_input_dir
    
    def get_ner_output_path(self) -> str:
        """Get output directory for NER results."""
        return self.ner_output_dir
    
    def get_preprocessing_output_path(self) -> str:
        """Get output directory for preprocessing results."""
        return self.ner_preprocessing_output_dir

    # -------------------------------------------------------------------------------------------
    # UTILITY METHODS
    # -------------------------------------------------------------------------------------------

    def ensure_directories(self):
        """
        Ensure all configured directories exist.
        Creates directories if they don't exist.
        """
        directories = [
            self.ner_preprocessing_output_dir,
            self.ner_output_dir,
            self.ontology_data_dir,
            self.ontology_scripts_dir,
            self.vocabulary_output_folder,
        ]
        
        # Add output folders
        directories.extend(self.ner_output_folders)
        directories.extend(self.dest_directories)
        
        for directory in directories:
            ensure_directory(directory)

    def validate_configuration(self) -> List[str]:
        """
        Validate the configuration and return any issues found.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check ontology directories
        if not os.path.exists(self.ontology_scripts_dir):
            errors.append(f"Ontology scripts directory not found: {self.ontology_scripts_dir}")
        
        # Check for required ontology script files
        required_scripts = ['extract_entities.sh', 'process_ontology.sh']
        for script in required_scripts:
            script_path = os.path.join(self.ontology_scripts_dir, script)
            if not os.path.exists(script_path):
                errors.append(f"Required script not found: {script_path}")
        
        # Check that active ontologies are configured
        for onto_name in self.active_lexicons:
            if onto_name.lower() not in self.ontologies:
                errors.append(f"Active ontology '{onto_name}' not found in configuration")
        
        # Check DrugBank file
        if not os.path.exists(self.drugbank_file):
            errors.append(f"DrugBank vocabulary file not found: {self.drugbank_file}")
        
        return errors

    def __repr__(self) -> str:
        """String representation of configuration."""
        return (
            f"DAGConfig(\n"
            f"  Active Ontologies: {', '.join(self.active_lexicons)}\n"
            f"  NER Input: {self.ner_input_dir}\n"
            f"  NER Output: {self.ner_output_dir}\n"
            f"  Ontology Data: {self.ontology_data_dir}\n"
            f"  Neo4j: {self.get_neo4j_uri()}\n"
            f")"
        )

# -------------------------------------------------------------------------------------------
# USAGE EXAMPLES
# -------------------------------------------------------------------------------------------

if __name__ == '__main__':
    """
    Example usage and self-test of the configuration class.
    Run this file directly to test the configuration loading.
    """
    
    print("-"*60)
    print("MedJsonIFY Configuration Test")
    print("-"*60)
    
    try:
        # Initialize configuration
        config = DAGConfig()
        
        print("\nConfiguration loaded successfully!\n")
        print(config)
        
        # Test ontology configuration
        print("\n" + "-"*60)
        print("ONTOLOGY CONFIGURATION")
        print("-"*60)
        
        print(f"\nOntology Data Directory: {config.ontology_data_dir}")
        print(f"Ontology Scripts Directory: {config.ontology_scripts_dir}")
        
        print(f"\nActive Ontologies: {', '.join(config.get_active_ontologies())}")
        print(f"Update Enabled: {config.ontology_update_enabled}")
        
        print("\nConfigured Ontologies:")
        for onto_name, onto_config in config.get_all_ontology_configs().items():
            active = " " if config.is_ontology_active(onto_name) else " "
            print(f"  [{active}] {onto_name.upper()}: {onto_config['description']}")
            print(f"      URL: {onto_config['url']}")
        
        # Test Neo4j configuration
        print("\n" + "-"*60)
        print("NEO4J CONFIGURATION")
        print("-"*60)
        neo4j_config = config.get_neo4j_config()
        print(f"\nURI: {neo4j_config['uri']}")
        print(f"User: {neo4j_config['user']}")
        print(f"Password: {'*' * len(neo4j_config['password'])}")
        
        # Test path configuration
        print("\n" + "-"*60)
        print("PATH CONFIGURATION")
        print("-"*60)
        print(f"\nNER Input: {config.get_ner_input_path()}")
        print(f"NER Output: {config.get_ner_output_path()}")
        print(f"Preprocessing Output: {config.get_preprocessing_output_path()}")
        
        print("\nConversion Input Folders:")
        for folder in config.get_conversion_input_paths():
            print(f"  - {folder}")
        
        # Validate configuration
        print("\n" + "-"*60)
        print("CONFIGURATION VALIDATION")
        print("-"*60)
        errors = config.validate_configuration()
        if errors:
            print("\n⚠ Configuration issues found:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("\nConfiguration is valid!")
        
        print("\n" + "-"*60)
        print("Test Complete")
        print("-"*60)
        
    except Exception as e:
        print(f"\nError loading configuration: {e}")
        import traceback
        traceback.print_exc()