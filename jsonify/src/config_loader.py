import os
import configparser
from typing import List, Dict, Any, Optional

class ConfigLoader:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            self.config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
        else:
            self.config_path = config_path
            
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self) -> None:
        self.config.read(self.config_path)
    
    # -----------------------------------------------------------------------------------

    def get_file_types(self) -> List[str]:
        file_types_str = self.config.get('general', 'file_type', fallback='xml')
        return [file_type.strip() for file_type in file_types_str.split(',')]
    
    # -----------------------------------------------------------------------------------
    
    def get_conversion_method(self) -> str:
        return self.config.get('general', 'conversion_method', fallback='python')
    
    # -----------------------------------------------------------------------------------
    
    def get_base_input_folder(self) -> str:
        return os.path.abspath(self.config['folders']['base_input_folder'])
    
    # -----------------------------------------------------------------------------------
    
    def get_base_output_folder(self) -> str:
        return os.path.abspath(self.config['folders']['base_output_folder'])
    
    # -----------------------------------------------------------------------------------
    
    def get_log_file_path(self) -> str:
        return os.path.abspath(self.config['log_files']['log_file'])
    
    # -----------------------------------------------------------------------------------
    
    def get_unconverted_file_path(self) -> str:
        return os.path.abspath(self.config['log_files']['unconverted_file'])
    
    # -----------------------------------------------------------------------------------
    
    def get_processed_medications_file_path(self) -> str:
        return os.path.abspath(self.config['log_files']['processed_medications_file'])
    
    # -----------------------------------------------------------------------------------

    def get_summary_file_path(self) -> str:
        return os.path.abspath(self.config['log_files']['processing_summary_file'])

    # -----------------------------------------------------------------------------------
    
    def get_input_folder_for_type(self, file_type: str) -> str:
        return os.path.join(self.get_base_input_folder(), f"{file_type}_files")
    
    # -----------------------------------------------------------------------------------
    
    def get_output_folder_for_type(self, file_type: str) -> str:
        return os.path.join(self.get_base_output_folder(), f"{file_type}_results")
    
    # -----------------------------------------------------------------------------------
    
    def get_all_folders(self) -> Dict[str, Dict[str, str]]:
        result = {}
        for file_type in self.get_file_types():
            result[file_type] = {
                'input': self.get_input_folder_for_type(file_type),
                'output': self.get_output_folder_for_type(file_type)
            }
        return result