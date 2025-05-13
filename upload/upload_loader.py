###############################################################################
#                                                                             #  
# @file: upload_loader.py                                                     #  
# @description: Configuration loader class for the file upload process         #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This module provides a unified interface for accessing configuration        #
# parameters related to the file upload process. It reads settings from       #
# an INI file and provides methods to access various configuration values.    #
#                                                                             #  
###############################################################################

import os
import configparser

class UploadLoader:
    """
    Configuration loader for the file upload process.
    
    This class reads configuration from an INI file and provides methods
    to access various settings needed for the upload process, including
    download directories, destination paths, and source URLs.
    
    Attributes:
        config_path (str): Path to the configuration file
        config (ConfigParser): Parsed configuration object
    """
    
    def __init__(self, config_filename='upload.ini'):
        """
        Initialize the configuration loader.
        
        Args:
            config_filename (str): Name of the configuration file (default: 'upload.ini')
        """
        # Locate the configuration file in the same directory as this module
        self.config_path = os.path.join(os.path.dirname(__file__), config_filename)
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)
        
    def get_downloads_dir(self):
        """
        Get the directory where downloaded files are stored.
        
        Returns:
            str: Path to the downloads directory
        """
        return os.path.expanduser(self.config['general']['downloads_dir'])
    
    def get_selected_directories(self):
        """
        Get the list of selected directory sources from the configuration.
        
        Returns:
            list: List of directory source names (e.g., 'dailymed', 'purplebook')
        """
        return [i.strip("'").strip(" ") for i in self.config['general']['selected_url'].split(",")]
    
    def get_urls(self):
        """
        Get the download URLs for the selected directories.
        
        Returns:
            list: List of URLs corresponding to selected directories
        """
        selected_directories = self.get_selected_directories()
        return [self.config['urls'][name] for name in selected_directories]
    
    def get_dest_directories(self):
        """
        Get the destination directories for each selected source.
        
        Returns:
            list: List of destination directory paths
        """
        selected_directories = self.get_selected_directories()
        return [os.path.expanduser(self.config['dest_directory'][name]) for name in selected_directories]