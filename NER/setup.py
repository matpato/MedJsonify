#!/usr/bin/env python3
"""
Setup and Validation Script for Standalone NER Migration
========================================================

This script helps you:
1. Setup the directory structure
2. Download and process ontologies
3. Validate the installation
4. Test entity extraction

Usage:
    python setup_standalone_bioner.py [--setup] [--download] [--validate] [--test]
"""

import argparse
import os
import sys
from pathlib import Path
import subprocess

def create_directory_structure(base_dir='.'):
    """Create required directory structure"""
    print("\n" + "="*60)
    print("Creating Directory Structure")
    print("="*60)
    
    base = Path(base_dir)
    
    directories = [
        'ontologies/data',
        'ontologies/scripts',
        'data/blacklists',
        'data/preprocessing',
    ]
    
    for dir_path in directories:
        full_path = base / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"Created: {full_path}")
    
    print("\nDirectory structure created successfully!\n")

def copy_scripts(base_dir='.'):
    """Copy shell scripts to the scripts directory"""
    print("\n" + "="*60)
    print("Setting Up Shell Scripts")
    print("="*60)
    
    base = Path(base_dir)
    scripts_dir = base / 'ontologies' / 'scripts'
    
    # Check if scripts exist in current directory
    scripts = ['extract_entities.sh', 'process_ontology.sh', 'rename_lexicon.sh']
    
    for script_name in scripts:
        if Path(script_name).exists():
            target = scripts_dir / script_name
            subprocess.run(['cp', script_name, str(target)])
            subprocess.run(['chmod', '+x', str(target)])
            print(f"Copied and made executable: {script_name}")
        else:
            print(f"⚠ Warning: {script_name} not found in current directory")
    
    print("\nScripts setup complete!\n")

def download_ontologies(base_dir='.'):
    """Download and process ontologies"""
    print("\n" + "="*60)
    print("Downloading and Processing Ontologies")
    print("="*60)
    
    try:
        from standalone_bioner import StandaloneBioNER
    except ImportError:
        print("ERROR: standalone_bioner.py not found")
        print("Please ensure standalone_bioner.py is in the current directory")
        return False
    
    base = Path(base_dir)
    data_dir = str(base / 'ontologies' / 'data')
    scripts_dir = str(base / 'ontologies' / 'scripts')
    
    # Initialize NER
    ner = StandaloneBioNER(data_dir=data_dir, scripts_dir=scripts_dir)
    
    # Check dependencies
    if not ner.check_dependencies():
        print("ERROR: Missing dependencies")
        return False
    
    if not ner.check_scripts():
        print("ERROR: Shell scripts not found")
        return False
    
    # Ontologies to download
    ontologies = [
        {
            'url': 'http://purl.obolibrary.org/obo/doid.owl',
            'name': 'doid',
            'description': 'Disease Ontology'
        },
        {
            'url': 'http://purl.obolibrary.org/obo/chebi/chebi_lite.owl',
            'name': 'chebi',
            'description': 'ChEBI Lite - Chemical Entities'
        },
        {
            'url': 'http://purl.obolibrary.org/obo/hp.owl',
            'name': 'hpo',
            'description': 'Human Phenotype Ontology'
        },
        {
            'url': 'https://www.orphadata.com/data/ontologies/ordo/last_version/ORDO_en_4.8.owl',
            'name': 'ordo',
            'description': 'Orphanet Rare Disease Ontology'
        }
    ]
    
    # Download and process
    print("\nThis may take several minutes...\n")
    results = ner.add_ontologies(ontologies)
    
    print("\n" + "="*60)
    print(f"Successfully processed {len(results)} ontologies")
    print("="*60)
    
    return True

def validate_installation(base_dir='.'):
    """Validate that everything is set up correctly"""
    print("\n" + "="*60)
    print("Validating Installation")
    print("="*60)
    
    base = Path(base_dir)
    data_dir = base / 'ontologies' / 'data'
    scripts_dir = base / 'ontologies' / 'scripts'
    
    issues = []
    
    # Check directory structure
    print("\n1. Checking directory structure...")
    required_dirs = ['ontologies/data', 'ontologies/scripts']
    for dir_path in required_dirs:
        if not (base / dir_path).exists():
            issues.append(f"Missing directory: {dir_path}")
        else:
            print(f"  {dir_path}")
    
    # Check scripts
    print("\n2. Checking shell scripts...")
    required_scripts = ['extract_entities.sh', 'process_ontology.sh']
    for script in required_scripts:
        script_path = scripts_dir / script
        if not script_path.exists():
            issues.append(f"Missing script: {script}")
        elif not os.access(script_path, os.X_OK):
            issues.append(f"Script not executable: {script}")
        else:
            print(f"  {script}")
    
    # Check ontology files
    print("\n3. Checking ontology data files...")
    ontologies = ['doid', 'chebi', 'hpo', 'ordo']
    for onto in ontologies:
        files_ok = True
        for suffix in ['_word1.txt', '_word2.txt', '_words.txt', '_words2.txt']:
            file_path = data_dir / f"{onto}{suffix}"
            if not file_path.exists():
                files_ok = False
                break
        
        if files_ok:
            print(f"  {onto}")
        else:
            print(f"  {onto} (missing files)")
    
    # Check Python dependencies
    print("\n4. Checking Python dependencies...")
    try:
        import subprocess
        print("  subprocess")
    except ImportError:
        issues.append("Missing Python module: subprocess")
    
    try:
        from pathlib import Path
        print("  pathlib")
    except ImportError:
        issues.append("Missing Python module: pathlib")
    
    # System dependencies
    print("\n5. Checking system dependencies...")
    for cmd in ['bash', 'grep', 'awk', 'sed']:
        result = subprocess.run(['which', cmd], capture_output=True)
        if result.returncode == 0:
            print(f"  {cmd}")
        else:
            issues.append(f"Missing system command: {cmd}")
    
    # Summary
    print("\n" + "="*60)
    if issues:
        print("Validation FAILED")
        print("\nIssues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nPlease fix these issues and run validation again.")
        return False
    else:
        print("Validation PASSED")
        print("\nAll components are properly installed!")
        return True

def test_extraction(base_dir='.'):
    """Test entity extraction"""
    print("\n" + "="*60)
    print("Testing Entity Extraction")
    print("="*60)
    
    base = Path(base_dir)
    data_dir = str(base / 'ontologies' / 'data')
    scripts_dir = str(base / 'ontologies' / 'scripts')
    
    # Test cases
    test_cases = [
        ("glucose", "chebi", "ChEBI extraction"),
        ("asthma", "do", "DOID extraction"),
        ("diabetes and hypertension", "do", "Multiple DOID entities"),
    ]
    
    print("\nRunning tests...\n")
    
    for text, onto, description in test_cases:
        print(f"Test: {description}")
        print(f"  Input: '{text}' (ontology: {onto})")
        
        # Map onto to lexicon name
        lexicon_map = {'chebi': 'chebi', 'do': 'doid'}
        lexicon = lexicon_map.get(onto, onto)
        
        # Run extraction
        extract_script = scripts_dir / 'extract_entities.sh'
        
        try:
            result = subprocess.run(
                [str(extract_script), text, lexicon, data_dir],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                print(f"  Success!")
                print(f"  Results:")
                for line in result.stdout.strip().split('\n')[:3]:  # Show first 3
                    print(f"    {line}")
                if len(result.stdout.strip().split('\n')) > 3:
                    print(f"    ... ({len(result.stdout.strip().split('\n')) - 3} more)")
            else:
                print(f"  No results found")
                if result.stderr:
                    print(f"  Error: {result.stderr}")
        
        except Exception as e:
            print(f"  Error: {e}")
        
        print()
    
    print("="*60)
    print("Testing complete!")

def main():
    parser = argparse.ArgumentParser(
        description='Setup and validate Standalone NER installation'
    )
    parser.add_argument('--setup', action='store_true',
                       help='Create directory structure')
    parser.add_argument('--copy-scripts', action='store_true',
                       help='Copy shell scripts to scripts directory')
    parser.add_argument('--download', action='store_true',
                       help='Download and process ontologies')
    parser.add_argument('--validate', action='store_true',
                       help='Validate installation')
    parser.add_argument('--test', action='store_true',
                       help='Test entity extraction')
    parser.add_argument('--all', action='store_true',
                       help='Run all steps (setup, download, validate, test)')
    parser.add_argument('--base-dir', default='.',
                       help='Base directory for installation (default: current directory)')
    
    args = parser.parse_args()
    
    # If no arguments, show help
    if not any([args.setup, args.copy_scripts, args.download, 
                args.validate, args.test, args.all]):
        parser.print_help()
        return
    
    # Run all steps
    if args.all:
        args.setup = True
        args.copy_scripts = True
        args.download = True
        args.validate = True
        args.test = True
    
    # Execute steps
    if args.setup:
        create_directory_structure(args.base_dir)
    
    if args.copy_scripts:
        copy_scripts(args.base_dir)
    
    if args.download:
        if not download_ontologies(args.base_dir):
            print("\nDownload failed. Please check the error messages above.")
            sys.exit(1)
    
    if args.validate:
        if not validate_installation(args.base_dir):
            print("\nValidation failed. Please fix the issues above.")
            sys.exit(1)
    
    if args.test:
        test_extraction(args.base_dir)
    
    print("\n" + "="*60)
    print("Setup Complete!")
    print("="*60)
    print("\nYou can now use the standalone NER system:")
    print("  from standalone_bioner import StandaloneBioNER")
    print("  ner = StandaloneBioNER()")
    print("  entities = ner.extract_entities('diabetes', 'doid')")
    print()

if __name__ == '__main__':
    main()