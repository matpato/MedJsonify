# NER Directory Structure - Standalone BioNER System

## Overview
This directory contains the Named Entity Recognition (NER) system for biomedical text processing using standalone shell-based ontology processing.

## Directory Structure

```
NER/
├── __init__.py 
├── standalone_bioner.py           # Main standalone BioNER class
├── ner_entities.py                # Core entity processing logic
├── ner_entities_batch.py          # Batch processing for multiple files
├── ner_drugbank.py                # DrugBank vocabulary matching
├── Biomedical_preprocessing.py    # Text preprocessing utilities
├── download_vocabulary.py         # Vocabulary download utilities
├── metrics.py                     # Add Metrics Collection     
├── validators.py                  # Add Data Validation 
├── logging_config.py              # Add Logging Configuration 
├── setup.py                       # Setup and validation script
│
├──  tests/                              
│    ├── __init__.py
│    ├── test_standalone_bioner.py
│    ├── test_ner_entities.py
│    └── test_preprocessing.py
│ 
├── ontologies/                        # Ontology management
│   ├── data/                          # Processed ontology data files
│   │   ├── doid_word1.txt             # Single-word entities (Disease Ontology)
│   │   ├── doid_word2.txt             # Two-word entities
│   │   ├── doid_words.txt             # All words vocabulary
│   │   ├── doid_words2.txt            # Two-word combinations
│   │   ├── doid_links.tsv             # Entity-URI mappings
│   │   ├── chebi_*.txt                # ChEBI ontology files
│   │   ├── hpo_*.txt                  # Human Phenotype Ontology files
│   │   ├── ordo_*.txt                 # Orphanet ontology files
│   │   └── metadata.json              # Ontology processing metadata
│   │
│   └── scripts/                       # Shell scripts for ontology processing
│       ├── extract_entities.sh        # Entity extraction script
│       ├── process_ontology.sh        # Ontology processing script
│       └── rename_lexicon.sh          # Lexicon renaming utility
│
├── data/                              # Data files and outputs
│   ├── drugbank_vocabulary.csv        # DrugBank reference vocabulary
│   ├── blacklists/                    # Entity blacklists
│   │   └── blacklist.txt
│   ├── entities/                      # Final NER output (by source type)
│   │   ├── xml_files/
│   │   ├── csv_files/
│   │   └── txt_files/
│   └── preprocessing/                 # Intermediate preprocessing results
│       ├── xml_files/
│       ├── csv_files/
│       └── txt_files/
│
└── bioner.ini                         # Main configuration file

```

## Configuration

### bioner.ini Sections

#### [PATH]
- **path_to_entities_json**: Final output directory for NER results
- **input_json_dir**: Input directory containing JSON files to process
- **preprocessing_output_dir**: Intermediate preprocessing output
- **ontology_data_dir**: Directory for ontology data files
- **ontology_scripts_dir**: Directory for shell scripts
- **drugbank_file**: Path to DrugBank vocabulary CSV

#### [ONTO]
- **active_lexicons**: Comma-separated list of ontologies to use (doid, chebi, hp, ordo)
- **update**: Whether to update ontologies (1=yes, 0=no)

#### [VOCABULARY]
- **drugbank_url**: URL to download DrugBank vocabulary
- **output_folder**: Where to save downloaded vocabularies

#### [ONTOLOGIES]
Defines URLs and metadata for each ontology:
- **{ontology}_url**: Download URL
- **{ontology}_name**: Lexicon name
- **{ontology}_description**: Human-readable description

Supported ontologies:
- **doid**: Disease Ontology
- **chebi**: Chemical Entities of Biological Interest
- **hpo**: Human Phenotype Ontology
- **ordo**: Orphanet Rare Disease Ontology

## Setup Instructions

### 1. Initial Setup

```bash
# Navigate to NER directory
cd /opt/airflow/dags/NER

# Run setup script to create directory structure
python setup.py --setup

# Copy shell scripts to the scripts directory
python setup.py --copy-scripts

# Download and process ontologies
python setup.py --download

# Validate installation
python setup.py --validate

# Test entity extraction
python setup.py --test

# Or run all steps at once
python setup.py --all
```

### 2. Download Vocabularies

```bash
# Download DrugBank and other vocabularies
python download_vocabulary.py
```

### 3. Verify Installation

```bash
# Check that all required files are present
python setup.py --validate
```

## Usage

### Basic Entity Extraction

```python
from src.standalone_bioner import StandaloneBioNER

# Initialize NER
ner = StandaloneBioNER(
    data_dir='./ontologies/data',
    scripts_dir='./ontologies/scripts'
)

# Extract entities
entities = ner.extract_entities('diabetes and hypertension', 'doid')

for entity in entities:
    print(f"{entity['text']}: {entity['uri']}")
```

### Batch Processing

```python
from src.ner_entities_batch import main
import configparser

# Load configuration
config = configparser.ConfigParser()
config.read('bioner.ini')

# Extract settings
active_lexicons = config.get('ONTO', 'active_lexicons').split(',')
input_dir = config.get('PATH', 'input_json_dir')
output_dir = config.get('PATH', 'preprocessing_output_dir')
drugbank_file = config.get('PATH', 'drugbank_file')
data_dir = config.get('STANDALONE_NER', 'data_dir')
scripts_dir = config.get('STANDALONE_NER', 'scripts_dir')

# Run batch processing
main(
    active_lexicon=active_lexicons,
    input_dir=input_dir,
    output_dir=output_dir,
    update='1',
    drugbank_file=drugbank_file,
    data_dir=data_dir,
    scripts_dir=scripts_dir
)
```

### Text Preprocessing

```python
from src.Biomedical_preprocessing import BiomedicalPreprocessor

# Initialize preprocessor
preprocessor = BiomedicalPreprocessor(
    preserve_case=False,
    keep_punctuation=True,
    remove_stops=True
)

# Preprocess text
text = "Patient diagnosed with HTN and DM."
cleaned = preprocessor.preprocess_text(text)
print(cleaned)
# Output: "patient diagnosed with hypertension and diabetes mellitus"

# Batch process directory
preprocessor.preprocess_directory(
    input_dir='/path/to/input',
    output_dir='/path/to/output',
    fields_to_process=['indications', 'contraindications']
)
```

## Component Details

### standalone_bioner.py
Main class for NER operations:
- Download and process ontologies from URLs
- Extract entities from text
- Manage ontology metadata
- Verify lexicon integrity

### ner_entities.py
Core entity identification functions:
- `get_onto_id()`: Get ontology ID for entity name
- `extract_disease_entities()`: Extract disease entities from text
- `process_drug_data()`: Enrich drug data with ontology IDs
- `find_disease_in_ontology()`: Find diseases in Orphanet

### ner_entities_batch.py
Batch processing capabilities:
- Process multiple JSON files in parallel
- Setup ontologies automatically
- Build disease dictionaries
- Concurrent processing with ThreadPoolExecutor

### ner_drugbank.py
DrugBank vocabulary matching:
- Fuzzy string matching using Jaro-Winkler distance
- Create searchable drug vocabulary
- Map drug names to DrugBank IDs
- Cache results for performance

### Biomedical_preprocessing.py
Text preprocessing utilities:
- Fix encoding issues
- Expand abbreviations
- Correct drug name spellings
- Remove stopwords
- Standardize punctuation

### download_vocabulary.py
Vocabulary download utilities:
- Download ZIP files from URLs
- Extract contents
- Find CSV files
- Return file paths

## Shell Scripts

### extract_entities.sh
Extracts entities from text using processed ontology files.

**Usage:**
```bash
./extract_entities.sh "text to analyze" "lexicon_name" "/path/to/data/dir"
```

**Output:**
```
START_POS   END_POS   MATCHED_TEXT   ENTITY_URI
```

### process_ontology.sh
Processes an ontology file (OWL/RDF) into searchable text files.

**Usage:**
```bash
./process_ontology.sh /path/to/ontology.owl /path/to/output/dir
```

**Outputs:**
- `{name}_word1.txt`: Single-word entities
- `{name}_word2.txt`: Two-word entities
- `{name}_words.txt`: All words
- `{name}_words2.txt`: Two-word combinations
- `{name}_links.tsv`: Entity-URI mappings

## Dependencies

### System Requirements
- bash
- gawk
- sed
- grep
- awk

### Python Requirements
- pandas
- requests
- Levenshtein (for fuzzy matching)
- nltk
- rdkit (optional, for chemistry)

## Troubleshooting

### Missing Shell Scripts
```bash
# Copy scripts from source
cp /path/to/scripts/*.sh ontologies/scripts/
chmod +x ontologies/scripts/*.sh
```

### Ontology Download Failures
```bash
# Manual download
wget http://purl.obolibrary.org/obo/doid.owl -O ontologies/data/doid.owl

# Process manually
./ontologies/scripts/process_ontology.sh ontologies/data/doid.owl ontologies/data
```

### Entity Extraction Returns No Results
1. Verify lexicon files exist: `ls ontologies/data/{lexicon}_*.txt`
2. Check script permissions: `ls -l ontologies/scripts/*.sh`
3. Validate with test: `python setup.py --test`

### DrugBank Vocabulary Missing
```bash
# Download manually
python download_vocabulary.py
```

## Integration with Airflow DAG

The NER system integrates with Airflow through the DAGConfig class:

```python
from utils.config import DAGConfig

config = DAGConfig()

# Access NER configuration
input_dir = config.input_json_dir
output_dir = config.preprocessing_output_dir
active_lexicons = config.active_lexicon
drugbank_file = config.drugbank_file
```

## Maintenance

### Updating Ontologies
```bash
# Update all ontologies to latest versions
python -c "
from src.standalone_bioner import StandaloneBioNER
ner = StandaloneBioNER()
for onto in ['doid', 'chebi', 'hpo', 'ordo']:
    ner.update_ontology(onto)
"
```

### Clearing Cache
```bash
# Remove processed ontology files
rm ontologies/data/*_word*.txt
rm ontologies/data/*_links.tsv
rm ontologies/data/metadata.json

# Re-download and process
python setup.py --download
```

## Performance Optimization

### Caching
Entity lookups are cached in memory during processing. For long-running processes, consider:
- Batch processing multiple files together
- Using `ThreadPoolExecutor` for parallel processing
- Pre-loading ontologies at startup

### Parallel Processing
```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    results = executor.map(process_file, file_list)
```

## License and Attribution

This NER system uses:
- **Disease Ontology (DOID)**: CC BY 4.0
- **ChEBI**: CC BY 4.0
- **Human Phenotype Ontology (HPO)**: Custom license
- **Orphanet (ORDO)**: CC BY 4.0
- **DrugBank**: Academic license required

Please ensure compliance with individual ontology licenses.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Run validation: `python setup.py --validate`
3. Review logs in `/opt/airflow/logs`
4. Contact the maintainer

## Version History

- **v2.1** (2026-01-02): Reorganized structure, added ontology configuration
- **v2.0** (2025-12-31): Migrated to standalone NER
- **v1.x**: Original MER-based implementation