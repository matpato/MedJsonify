import time
from functools import wraps
import json
from pathlib import Path

class NERMetrics:
    """Collect and report NER processing metrics"""
    
    def __init__(self):
        self.metrics = {
            'ontology_downloads': {},
            'file_processing': {},
            'entity_counts': {},
            'processing_times': {}
        }
    
    def record_ontology_download(self, name: str, success: bool, duration: float):
        """Record ontology download metrics"""
        self.metrics['ontology_downloads'][name] = {
            'success': success,
            'duration_seconds': duration,
            'timestamp': time.time()
        }
    
    def record_file_processing(self, file_path: str, entities_found: int, duration: float):
        """Record file processing metrics"""
        self.metrics['file_processing'][file_path] = {
            'entities_found': entities_found,
            'duration_seconds': duration,
            'timestamp': time.time()
        }
    
    def save_report(self, output_path: str):
        """Save metrics report"""
        report = {
            'summary': {
                'total_files_processed': len(self.metrics['file_processing']),
                'total_ontologies': len(self.metrics['ontology_downloads']),
                'total_entities': sum(
                    m['entities_found'] 
                    for m in self.metrics['file_processing'].values()
                ),
                'total_processing_time': sum(
                    m['duration_seconds'] 
                    for m in self.metrics['file_processing'].values()
                )
            },
            'details': self.metrics
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

# Decorator for timing functions
def timed_metric(metrics_collector: NERMetrics, metric_name: str):
    """Decorator to time function execution"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            
            print(f"{metric_name} completed in {duration:.2f}s")
            return result
        return wrapper
    return decorator