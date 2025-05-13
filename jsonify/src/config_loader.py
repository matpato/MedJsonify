###############################################################################
#                                                                             #  
# @file: config_loader.py                                                     #  
# @description: Configuration loading and management for the conversion system #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This module provides a centralized configuration management system for      #
# the file conversion pipeline. It handles loading settings from the config   #
# file and provides typed accessor methods for all configuration parameters.  #
#                                                                             #  
###############################################################################

import os
import configparser
from typing import List, Dict, Any, Optional

class ConfigLoader:
    """
    Configuration loader for the file conversion system.
    
    This class handles loading and accessing configuration parameters from the config.ini file,
    providing a consistent interface for retrieving configuration values throughout the application.
    
    Attributes:
        config_path (str): Path to the configuration file
        config (ConfigParser): Parsed configuration object
    """
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration loader.
        
        Args:
            config_path (Optional[str]): Path to the configuration file. If None, the default 
                                         path is used (parent directory's config.ini).
        """
        # OBJECTIVE: Determine the configuration file path
        if config_path is None:
            # Default path is one directory up from this file
            self.config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
        else:
            self.config_path = config_path
            
        # Initialize the configuration parser
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self) -> None:
        """
        Load the configuration from the specified file.
        """
        # OBJECTIVE: Read and parse the configuration file
        self.config.read(self.config_path)
    
    # -----------------------------------------------------------------------------------
    # FILE TYPE CONFIGURATION
    # -----------------------------------------------------------------------------------

    def get_file_types(self) -> List[str]:
        """
        Get the list of file types to process from the configuration.
        
        Returns:
            List[str]: List of file types (e.g., ['xml', 'csv', 'txt'])
        """
        # OBJECTIVE: Extract and parse the list of file types
        file_types_str = self.config.get('general', 'file_type', fallback='xml')
        return [file_type.strip() for file_type in file_types_str.split(',')]
    

    
    def get_conversion_method(self) -> str:
        """
        Get the conversion method to use for XML files.
        
        Returns:
            str: The conversion method ('python' or 'xslt')
        """
        # OBJECTIVE: Get the configured conversion method with default fallback
        return self.config.get('general', 'conversion_method', fallback='python')
    
    # -----------------------------------------------------------------------------------
    # FOLDER CONFIGURATION
    # -----------------------------------------------------------------------------------
    
    def get_base_input_folder(self) -> str:
        """
        Get the base directory for input files.
        
        Returns:
            str: Absolute path to the base input folder
        """
        # OBJECTIVE: Get the configured base input folder as an absolute path
        return os.path.abspath(self.config['folders']['base_input_folder'])
    

    
    def get_base_output_folder(self) -> str:
        """
        Get the base directory for output files.
        
        Returns:
            str: Absolute path to the base output folder
        """
        # OBJECTIVE: Get the configured base output folder as an absolute path
        return os.path.abspath(self.config['folders']['base_output_folder'])
    
    # -----------------------------------------------------------------------------------
    # LOG FILE CONFIGURATION
    # -----------------------------------------------------------------------------------
    
    def get_log_file_path(self) -> str:
        """
        Get the path to the main log file.
        
        Returns:
            str: Absolute path to the log file
        """
        # OBJECTIVE: Get the configured log file path as an absolute path
        return os.path.abspath(self.config['log_files']['log_file'])
    

    
    def get_unconverted_file_path(self) -> str:
        """
        Get the path to the log file for unconverted files.
        
        Returns:
            str: Absolute path to the unconverted files log
        """
        # OBJECTIVE: Get the configured unconverted file log path as an absolute path
        return os.path.abspath(self.config['log_files']['unconverted_file'])
    

    
    def get_processed_medications_file_path(self) -> str:
        """
        Get the path to the file tracking processed medications.
        
        Returns:
            str: Absolute path to the processed medications file
        """
        # OBJECTIVE: Get the configured processed medications file path as an absolute path
        return os.path.abspath(self.config['log_files']['processed_medications_file'])
    


    def get_summary_file_path(self) -> str:
        """
        Get the path to the processing summary log file.
        
        Returns:
            str: Absolute path to the processing summary file
        """
        # OBJECTIVE: Get the configured summary file path as an absolute path
        return os.path.abspath(self.config['log_files']['processing_summary_file'])

    # -----------------------------------------------------------------------------------
    # DERIVED FOLDER PATHS
    # -----------------------------------------------------------------------------------
    
    def get_input_folder_for_type(self, file_type: str) -> str:
        """
        Get the input folder for a specific file type.
        
        Args:
            file_type (str): The file type (e.g., 'xml', 'csv')
            
        Returns:
            str: The absolute path to the input folder for the specified file type
        """
        # OBJECTIVE: Generate the input folder path for a specific file type
        return os.path.join(self.get_base_input_folder(), f"{file_type}_files")
    

    
    def get_output_folder_for_type(self, file_type: str) -> str:
        """
        Get the output folder for a specific file type.
        
        Args:
            file_type (str): The file type (e.g., 'xml', 'csv')
            
        Returns:
            str: The absolute path to the output folder for the specified file type
        """
        # OBJECTIVE: Generate the output folder path for a specific file type
        return os.path.join(self.get_base_output_folder(), f"{file_type}_results")

    
    def get_all_folders(self) -> Dict[str, Dict[str, str]]:
        """
        Get all input and output folders for all configured file types.
        
        Returns:
            Dict[str, Dict[str, str]]: A dictionary mapping file types to their
                                       input and output folder paths
        """
        # OBJECTIVE: Build a mapping of all file types to their input/output directories
        result = {}
        for file_type in self.get_file_types():
            result[file_type] = {
                'input': self.get_input_folder_for_type(file_type),
                'output': self.get_output_folder_for_type(file_type)
            }
        return result