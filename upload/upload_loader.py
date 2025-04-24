import os
import configparser

class UploadLoader:
    def __init__(self, config_filename='upload.ini'):
        self.config_path = os.path.join(os.path.dirname(__file__), config_filename)
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)
        
    def get_downloads_dir(self):
        return os.path.expanduser(self.config['general']['downloads_dir'])
    
    def get_selected_directories(self):
        return [i.strip("'").strip(" ") for i in self.config['general']['selected_url'].split(",")]
    
    def get_urls(self):
        selected_directories = self.get_selected_directories()
        return [self.config['urls'][name] for name in selected_directories]
    
    def get_dest_directories(self):
        selected_directories = self.get_selected_directories()
        return [os.path.expanduser(self.config['dest_directory'][name]) for name in selected_directories]
