# MedJsonify
<div id="top"></div>
<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->

[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Available-blue.svg)](https://www.docker.com/)
[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-017CEE?style=for-the-badge&logo=Apache%20Airflow&logoColor=white)](https://airflow.apache.org)
[![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?logo=neo4j&logoColor=white)](https://neo4j.com/)
[![NLTK](https://img.shields.io/badge/NLTK-3776AB?logo=python&logoColor=fff)](https://www.nltk.org)
[![Pandas](https://img.shields.io/badge/Pandas-150458?logo=pandas&logoColor=fff)](https://pandas.pydata.org)
[![Website](https://img.shields.io/website-up-down-green-red/http/shields.io.svg)](https://shields.io/)

## Overview

MedJsonify is a comprehensive biomedical data processing pipeline that extracts, transforms, and analyzes pharmaceutical information from various data sources. The framework converts multiple input formats (XML, CSV, TXT) into standardized JSON, performs Named Entity Recognition (NER) to extract biomedical entities, and builds a knowledge graph in Neo4j to represent relationships between drugs, diseases, and other medical concepts.

<div align="center">
  <img src="./img/airflow_orchestration.png" width="600" alt="Airflow Orchestration Diagram"/>
</div>

## Table of Contents

1. [Project Structure](#project-structure)
2. [Key Features](#key-features)
3. [Technologies](#technologies)
4. [Installation](#installation)
5. [Usage](#usage)
6. [Pipeline Workflow](#pipeline-workflow)
7. [License](#license)
8. [How to Cite](#how-to-cite)

## Project Structure

The project is organized into several key modules, each responsible for specific aspects of the data processing pipeline:

```
medjsonify/
├── img/                          # Images and documentation resources
├── airflow/                      # Apache Airflow configuration and DAG files
│   ├── dags/                     # DAG definition files
│   │   ├── utils/                # Utility functions for DAGs
│   │   ├── airflow.ini          # Airflow configuration
│   │   ├── converter_dag.py     # DAG for file conversion process
│   │   ├── create_user.py       # Script to create Airflow users
│   │   ├── jsonify_dag.py       # Complete data processing pipeline DAG
│   │   ├── neo4j_dag.py         # DAG for Neo4j database operations
│   │   └── ner_dag.py           # DAG for Named Entity Recognition
├── database/                     # Neo4j database integration
│   ├── knowledge_graph.py       # Knowledge graph implementation
│   ├── neo4j.ini                # Neo4j connection configuration
│   └── queries.md               # Example Neo4j queries
├── upload/                       # Data acquisition and preprocessing
│   ├── download_from_url.py     # Download files from URLs
│   ├── extract_files.py         # Extract files from archives
│   ├── unzip_directories.py     # Extract ZIP archives
│   └── upload_loader.py         # Configuration for upload process
├── NER/                          # Named Entity Recognition processing
│   ├── data/                     # Data for NER processing
│   │   ├── blacklists/          # Lists of terms to exclude
│   │   ├── entities/            # Entity dictionaries
│   │   └── preprocessing/       # Preprocessed text data
│   ├── src/                      # NER source code
│   │   ├── Utils/               # Utility functions for NER
│   │   ├── mer_entities.py      # Basic entity extraction
│   │   ├── mer_entities_batch.py # Batch entity extraction
│   │   ├── ner_drugbank.py      # DrugBank entity processing
│   │   └── ner_onto.py          # Ontology-based entity processing
│   ├── Biomedical_preprocessing.py # Text preprocessing for biomedical data
│   └── download_vocabulary.py    # Download ontology vocabularies
├── jsonify/                      # File format conversion module
│   ├── src/                      # Conversion source code
│   │   ├── converter/           # Converter implementations
│   │   │   ├── csv_converter.py  # CSV to JSON conversion
│   │   │   ├── python_converter.py # Python-based XML to JSON conversion
│   │   │   └── xslt_converter.py # XSLT-based XML to JSON conversion
│   │   └── main.py              # Main conversion driver
├── Dockerfile                    # Docker container definition
├── docker-compose.yml           # Docker Compose configuration
├── docker.sh                    # Script to build and run containers
└── requirements.txt             # Python dependencies
```

## Key Features

- **Multi-format Data Processing**: Converts XML, CSV, and TXT files to standardized JSON format
- **Named Entity Recognition (NER)**: Extracts biomedical entities like drugs, diseases, and chemical compounds
- **Knowledge Graph Construction**: Creates a structured graph in Neo4j representing relationships between entities
- **Workflow Orchestration**: Uses Apache Airflow to manage and schedule the complete data pipeline
- **Containerized Deployment**: Packaged with Docker for easy deployment and environment consistency
- **Ontology Integration**: Leverages biomedical ontologies like ChEBI, Disease Ontology, and Orphanet

## Technologies

- **Python**: Core programming language
- **Apache Airflow**: Workflow orchestration and scheduling
- **Neo4j**: Graph database for knowledge representation
- **Docker**: Containerization for deployment
- **MER (Minimal Entity Recognition)**: Biomedical entity extraction
- **NLTK**: Natural Language Processing for text preprocessing
- **Pandas**: Data manipulation and transformation
- **lxml**: XML processing and XSLT transformations

## Installation

### Prerequisites

- Docker and Docker Compose
- Git

### Setup

1. Clone the repository:
```bash
git clone https://github.com/your-username/medjsonify.git
```

2. Navigate to the project directory:
```bash
cd medjsonify
```

3. Grant execution permissions to the Docker script:
```bash
chmod +x docker.sh
```

4. Ensure MER is installed and grant execution permissions to the entity extraction script:
```bash
chmod +x get_entities.sh
```

## Usage

1. Build and run the Docker containers:
```bash
./docker.sh
```

2. Access the Apache Airflow web interface:
```bash
http://localhost:8080
```

3. Log in with the default credentials:
   - Username: admin
   - Password: admin

4. From the Airflow UI, activate and trigger the desired DAG:
   - `converter_dag`: Only converts files to JSON
   - `ner_dag`: Processes JSON files with NER
   - `jsonify_dag`: Runs the complete pipeline

5. After processing, the Neo4j database will contain the knowledge graph. Access the Neo4j Browser:
```bash
http://localhost:7474
```

6. Example queries can be found in the `database/queries.md` file.

## Pipeline Workflow

The complete data processing pipeline consists of the following steps:

1. **Data Acquisition**:
   - Download files from configured URLs
   - Extract ZIP archives
   - Extract specific files based on type

2. **Data Conversion**:
   - Convert XML files using either Python-based parsing or XSLT
   - Convert CSV files with appropriate delimiters and headers
   - Convert TXT files with specified delimiters
   - Standardize to JSON format

3. **Named Entity Recognition**:
   - Download and update biomedical vocabularies and ontologies
   - Preprocess JSON text fields for NER
   - Extract drug and disease entities
   - Normalize entity identifiers to standard ontologies

4. **Knowledge Graph Construction**:
   - Create nodes for drugs, diseases, administration routes, and approval years
   - Establish relationships between entities (TREATS, CONTRAINDICATED_FOR, etc.)
   - Apply constraints to ensure data integrity

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## How to Cite

If you use MedJsonify in your research, please cite it as follows:

```
[Citation information will be added upon project publication]
```

---

<div align="center">
  <p>Developed at <a href=" ">TO BE DEFINED LATER</a></p>
</div>
