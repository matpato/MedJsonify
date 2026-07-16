"""
Standalone Biomedical NER - Direct URL Support

This module provides biomedical Named Entity Recognition using bash scripts directly,
with flexible URL-based ontology management.

Features:
- Works with any user permissions
- Direct URL specification for ontologies
- Automatic lexicon renaming (e.g., ORDO_en_4.8 -> ordo)
- No pre-configured sources needed
- Efficient batch processing
"""

import os
import subprocess
import urllib.request
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Union
from datetime import datetime


class StandaloneBioNER:
    """
    Standalone Biomedical Named Entity Recognition
    
    Uses bash scripts directly without merpy installation.
    Ontologies are specified by URL - no pre-configuration needed.
    """
    
    def __init__(self, 
                 data_dir: str = "./ontologies/data",
                 scripts_dir: str = "./ontologies/scripts"):
        """
        Initialize Standalone BioNER
        
        Args:
            data_dir: Directory to store ontology data files
            scripts_dir: Directory containing bash scripts
        """
        self.data_dir = Path(data_dir)
        self.scripts_dir = Path(scripts_dir)
        
        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        
        # Metadata file
        self.metadata_file = self.data_dir / "metadata.json"
        self.metadata = self._load_metadata()
        
        # Check for required scripts
        self.process_script = self.scripts_dir / "process_ontology.sh"
        self.extract_script = self.scripts_dir / "extract_entities.sh"
        self.rename_script = self.scripts_dir / "rename_lexicon.sh"
    
    def _load_metadata(self) -> Dict:
        """Load metadata about processed ontologies"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_metadata(self):
        """Save metadata about processed ontologies"""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def check_dependencies(self) -> bool:
        """Check if required bash commands are available"""
        required = ['bash', 'gawk', 'sed', 'grep', 'awk']
        missing = []
        
        for cmd in required:
            if shutil.which(cmd) is None:
                missing.append(cmd)
        
        if missing:
            print(f"ERROR: Missing required commands: {', '.join(missing)}")
            print("Please install them using your package manager")
            print("Example (Ubuntu/Debian): sudo apt-get install gawk")
            return False
        
        return True
    
    def check_scripts(self) -> bool:
        """Check if required bash scripts exist"""
        scripts_to_check = [
            (self.process_script, "process_ontology.sh"),
            (self.extract_script, "extract_entities.sh"),
            (self.rename_script, "rename_lexicon.sh")
            ]
        
        missing = []
        for script_path, script_name in scripts_to_check:
            if not script_path.exists():
                missing.append(script_name)
        
        if missing:
            print(f"ERROR: Missing scripts: {', '.join(missing)}")
            print(f"Please ensure they are in: {self.scripts_dir}")
            return False
        
        # Make scripts executable
        for script_path, _ in scripts_to_check:
            if script_path.exists():
                os.chmod(script_path, 0o755)
        
        return True
    
    def _extract_filename_from_url(self, url: str) -> str:
        """
        Extract the base filename from a URL
        
        Args:
            url: URL to extract filename from
            
        Returns:
            Base filename without extension
            
        Example:
            >>> _extract_filename_from_url(
            ...     'https://www.orphadata.com/data/ontologies/ordo/last_version/ORDO_en_4.8.owl'
            ... )
            'ORDO_en_4.8'
        """
        # Get the last part of the URL
        filename = url.split('/')[-1]
        
        # Remove extension
        base_name = os.path.splitext(filename)[0]
        
        return base_name
    
    def rename_lexicon(self, old_name: str, new_name: str) -> bool:
        """
        Rename all lexicon files from old_name to new_name
        
        Args:
            old_name: Current lexicon name prefix
            new_name: Desired lexicon name prefix
            
        Returns:
            True if successful
            
        Example:
            >>> ner = StandaloneBioNER()
            >>> ner.rename_lexicon('ORDO_en_4.8', 'ordo')
        """
        if not self.rename_script.exists():
            print(f"ERROR: Rename script not found: {self.rename_script}")
            return False
        
        print(f"\nRenaming lexicon from '{old_name}' to '{new_name}'...")
        
        try:
            result = subprocess.run(
                [str(self.rename_script), old_name, new_name, str(self.data_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            
            print(result.stdout)
            
            if result.stderr:
                print("Warnings:", result.stderr)
            
            print(f"Lexicon renamed successfully!")
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"Error renaming lexicon:")
            print(e.stdout)
            print(e.stderr)
            return False
    
    def health_check(self) -> dict:
        """
        Check system health and readiness
        
        Returns:
            dict: Health status report
        """
        status = {
            'dependencies': self.check_dependencies(),
            'scripts': self.check_scripts(),
            'ontologies': {},
            'overall': True
        }
        
        # Check each ontology
        for name in self.metadata.keys():
            status['ontologies'][name] = self.verify_lexicon(name)
        
        # Overall status
        status['overall'] = (
            status['dependencies'] and 
            status['scripts'] and 
            all(status['ontologies'].values())
        )
    
        return status

    def download_ontology(self, 
                         url: str,
                         name: str,
                         ontology_type: Optional[str] = None) -> Path:
        """
        Download an ontology file from URL
        
        Args:
            url: URL to download ontology from
            name: Name for the ontology (will be used as lexicon name)
            ontology_type: File type (owl, rdf, xml, txt). Auto-detected if None.
            
        Returns:
            Path to downloaded file
            
        Example:
            >>> ner = StandaloneBioNER()
            >>> ner.download_ontology(
            ...     'http://purl.obolibrary.org/obo/doid.owl',
            ...     'doid'
            ... )
        """
        # Auto-detect type from URL if not specified
        if ontology_type is None:
            if url.endswith('.owl'):
                ontology_type = 'owl'
            elif url.endswith('.rdf'):
                ontology_type = 'rdf'
            elif url.endswith('.xml'):
                ontology_type = 'xml'
            elif url.endswith('.txt'):
                ontology_type = 'txt'
            else:
                # Default to owl
                ontology_type = 'owl'
        
        output_file = self.data_dir / f"{name}.{ontology_type}"
        
        print(f"Downloading {name} from {url}...")
        
        try:
            with urllib.request.urlopen(url) as response:
                with open(output_file, 'wb') as out_file:
                    out_file.write(response.read())
            
            print(f"Downloaded to {output_file}")
            return output_file
        
        except Exception as e:
            print(f"Error downloading: {e}")
            raise
    
    def process_ontology(self, ontology_file: Path) -> bool:
        """
        Process an ontology file using bash script
        
        Args:
            ontology_file: Path to ontology file
            
        Returns:
            True if successful
        """
        if not self.check_scripts():
            return False
        
        print(f"Processing {ontology_file.name}...")
        
        try:
            result = subprocess.run(
                [str(self.process_script), str(ontology_file), str(self.data_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            
            print(result.stdout)
            
            if result.stderr:
                print("Warnings:", result.stderr)
            
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"Error processing ontology:")
            print(e.stdout)
            print(e.stderr)
            return False
    
    def add_ontology(self,
                     url: str,
                     name: str,
                     ontology_type: Optional[str] = None,
                     description: Optional[str] = None,
                     skip_if_exists: bool = True) -> Optional[str]:
        """
        Download and process an ontology from URL
        
        Args:
            url: URL to download ontology from
            name: Name for the lexicon
            ontology_type: File type (owl, rdf, xml, txt). Auto-detected if None.
            description: Optional description of the ontology
            skip_if_exists: Skip if already processed
            
        Returns:
            Lexicon name if successful, None otherwise
            
        Example:
            >>> ner = StandaloneBioNER()
            >>> ner.add_ontology(
            ...     url='http://purl.obolibrary.org/obo/doid.owl',
            ...     name='doid',
            ...     description='Disease Ontology'
            ... )
            'doid'
        """
        # Check dependencies first
        if not self.check_dependencies():
            return None
        
        if not self.check_scripts():
            return None
        
        # Check if already exists
        if skip_if_exists and name in self.metadata:
            print(f"{name} already processed (use skip_if_exists=False to reprocess)")
            return name
        
        try:
            # Download
            ontology_file = self.download_ontology(url, name, ontology_type)
            
            # Process
            if not self.process_ontology(ontology_file):
                return None
            
            # Update metadata
            self.metadata[name] = {
                'url': url,
                'type': ontology_type or ontology_file.suffix[1:],
                'description': description,
                'processed_at': datetime.now().isoformat(),
            }
            self._save_metadata()
            
            print(f"\n{name} is ready to use!")
            return name
        
        except Exception as e:
            print(f"Error setting up ontology: {e}")
            return None
    
    def add_ontologies(self, ontologies: List[Dict[str, str]]) -> List[str]:
        """
        Add multiple ontologies
        
        Args:
            ontologies: List of dictionaries with 'url', 'name', and optional 'type', 'description'
            
        Returns:
            List of successfully processed lexicon names
            
        Example:
            >>> ner = StandaloneBioNER()
            >>> ontologies = [
            ...     {
            ...         'url': 'http://purl.obolibrary.org/obo/doid.owl',
            ...         'name': 'doid',
            ...         'description': 'Disease Ontology'
            ...     },
            ...     {
            ...         'url': 'http://purl.obolibrary.org/obo/hp.owl',
            ...         'name': 'hpo',
            ...         'description': 'Human Phenotype Ontology'
            ...     }
            ... ]
            >>> ner.add_ontologies(ontologies)
            ['doid', 'hpo']
        """
        processed = []
        
        for ont in ontologies:
            print(f"\n{'='*60}")
            result = self.add_ontology(
                url=ont['url'],
                name=ont['name'],
                ontology_type=ont.get('type'),
                description=ont.get('description')
            )
            if result:
                processed.append(result)
            print(f"{'='*60}\n")
        
        return processed
    
    def extract_entities(self,
                        text: str,
                        lexicon_name: str) -> List[Dict]:
        """
        Extract entities from text
        
        Args:
            text: Text to analyze
            lexicon_name: Name of lexicon to use
            
        Returns:
            List of entity dictionaries with start, end, text, and optional uri
            
        Example:
            >>> ner = StandaloneBioNER()
            >>> entities = ner.extract_entities('diabetes and hypertension', 'doid')
            >>> for e in entities:
            ...     print(f"{e['text']}: {e['uri']}")
        """
        if not self.check_scripts():
            return []
        
        try:
            result = subprocess.run(
                [str(self.extract_script), text, lexicon_name, str(self.data_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            
            entities = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 3:
                    entity = {
                        'start': int(parts[0]),
                        'end': int(parts[1]),
                        'text': parts[2]
                    }
                    if len(parts) > 3:
                        entity['uri'] = parts[3]
                    
                    entities.append(entity)
            
            return entities
        
        except subprocess.CalledProcessError as e:
            print(f"Error extracting entities: {e.stderr}")
            return []
    
    def list_ontologies(self) -> Dict:
        """
        List all processed ontologies with their metadata
        
        Returns:
            Dictionary of ontology metadata
        """
        return self.metadata
    
    def show_ontologies(self):
        """Print formatted list of processed ontologies"""
        if not self.metadata:
            print("\nNo ontologies processed yet.")
            print("Use add_ontology() to add an ontology.\n")
            return
        
        print("\n=== Processed Ontologies ===\n")
        for name, info in self.metadata.items():
            print(f"{name.upper():15}")
            print(f"{'':15}   URL: {info['url'][:60]}...")
            if info.get('description'):
                print(f"{'':15}   Description: {info['description']}")
            print(f"{'':15}   Type: {info['type']}")
            print(f"{'':15}   Processed: {info['processed_at'][:10]}")
            
            # Count entities
            word1_file = self.data_dir / f"{name}_word1.txt"
            if word1_file.exists():
                with open(word1_file) as f:
                    count = sum(1 for _ in f)
                print(f"{'':15}   Entities: {count:,}")
            
            print()
    
    def get_ontology_info(self, name: str) -> Optional[Dict]:
        """
        Get metadata for a specific ontology
        
        Args:
            name: Ontology name
            
        Returns:
            Dictionary with ontology metadata or None
        """
        return self.metadata.get(name)
    
    def remove_ontology(self, name: str, delete_source: bool = False) -> bool:
        """
        Remove a processed ontology
        
        Args:
            name: Ontology name to remove
            delete_source: Also delete the source ontology file
            
        Returns:
            True if successful
        """
        if name not in self.metadata:
            print(f"Ontology '{name}' not found")
            return False
        
        try:
            # Remove processed files
            for suffix in ['_word1.txt', '_word2.txt', '_words.txt', '_words2.txt', 
                          '_links.tsv', '.txt']:
                file_path = self.data_dir / f"{name}{suffix}"
                if file_path.exists():
                    file_path.unlink()
            
            # Remove source file if requested
            if delete_source:
                ont_type = self.metadata[name].get('type', 'owl')
                source_file = self.data_dir / f"{name}.{ont_type}"
                if source_file.exists():
                    source_file.unlink()
            
            # Remove from metadata
            del self.metadata[name]
            self._save_metadata()
            
            print(f"Removed ontology: {name}")
            return True
        
        except Exception as e:
            print(f"Error removing ontology: {e}")
            return False
    
    def update_ontology(self, name: str) -> bool:
        """
        Update an ontology to the latest version
        
        Args:
            name: Ontology name to update
            
        Returns:
            True if successful
        """
        if name not in self.metadata:
            print(f"Ontology '{name}' not found")
            return False
        
        metadata = self.metadata[name]
        print(f"Updating {name}...")
        print(f"Previous version from: {metadata['processed_at']}")
        
        # Remove old version
        self.remove_ontology(name, delete_source=True)
        
        # Re-download and process
        result = self.add_ontology(
            url=metadata['url'],
            name=name,
            ontology_type=metadata.get('type'),
            description=metadata.get('description'),
            skip_if_exists=False
        )
        
        if result:
            print(f"{name} updated successfully!")
            return True
        else:
            print(f"Failed to update {name}")
            return False
    
    def verify_lexicon(self, lexicon_name: str) -> bool:
        """
        Verify that a lexicon has all required files
        
        Args:
            lexicon_name: Name of lexicon to verify
            
        Returns:
            True if all files exist
        """
        required_files = [
            f"{lexicon_name}_word1.txt",
            f"{lexicon_name}_word2.txt",
            f"{lexicon_name}_words.txt",
            f"{lexicon_name}_words2.txt"
        ]
        
        missing = []
        for filename in required_files:
            if not (self.data_dir / filename).exists():
                missing.append(filename)
        
        if missing:
            print(f"Missing files for {lexicon_name}:")
            for f in missing:
                print(f"  - {f}")
            return False
        
        return True


# Common ontology URLs (for reference/convenience)
COMMON_ONTOLOGIES = {
    'doid': {
        'url': 'http://purl.obolibrary.org/obo/doid.owl',
        'name': 'do',
        'type': "owl",
        'description': 'Disease Ontology - Human disease classifications'
    },
    'chebi': {
        'url': 'http://purl.obolibrary.org/obo/chebi/chebi_lite.owl',
        'name': 'chebi',
        'type': "owl",
        'description': 'ChEBI Lite - Chemical entities of biological interest'
    },
    'hpo': {
        'url': 'http://purl.obolibrary.org/obo/hp.owl',
        'name': 'hpo',
        'type': "owl",
        'description': 'Human Phenotype Ontology - Phenotypic abnormalities'
    },
    'ordo': {
        'url': 'https://www.orphadata.com/data/ontologies/ordo/last_version/ordo_orphanet.owl',
        'name': 'ordo',
        'type': "owl",
        'description': 'Orphanet Rare Disease Ontology'
    },
    'go': {
        'url': 'http://purl.obolibrary.org/obo/go.owl',
        'name': 'go',
        'type': "owl",
        'description': 'Gene Ontology - Gene and gene product attributes'
    },
    'cido': {
        'url': 'http://purl.obolibrary.org/obo/cido.owl',
        'name': 'cido',
        'type': "owl",
        'description': 'Ontology of Coronavirus Infectious Disease'

    },
    'mondo': {
        'url': 'http://purl.obolibrary.org/obo/mondo.owl',
        'description': 'Monarch Disease Ontology - Integrated disease ontology'
    },
    'uberon': {
        'url': 'http://purl.obolibrary.org/obo/uberon/basic.owl',
        'description': 'Uberon - Anatomical structures across species'
    },
}


def get_common_ontology_urls() -> Dict:
    """
    Get dictionary of common ontology URLs for reference
    
    Returns:
        Dictionary with ontology information
    """
    return COMMON_ONTOLOGIES


def show_common_ontologies():
    """Print list of common ontology URLs"""
    print("\n=== Common Ontology URLs (for reference) ===\n")
    for key, info in COMMON_ONTOLOGIES.items():
        print(f"{key.upper():10}")
        print(f"{'':10}   {info['description']}")
        print(f"{'':10}   URL: {info['url']}")
        print()


if __name__ == '__main__':
    # Example usage
    print("Standalone BioNER - Direct URL Support\n")
    
    # Create instance
    ner = StandaloneBioNER(data_dir="./data", scripts_dir="./scripts")
    
    # Show common ontologies for reference
    show_common_ontologies()
    
    # Show processed ontologies
    ner.show_ontologies()
    
    print("\nTo add an ontology:")
    print("  ner.add_ontology(")
    print("      url='http://purl.obolibrary.org/obo/doid.owl',")
    print("      name='doid',")
    print("      description='Disease Ontology'")
    print("  )")
    print("\nTo extract entities:")
    print("  entities = ner.extract_entities('diabetes', 'doid')")