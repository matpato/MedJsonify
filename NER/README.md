# NER

This module contains the Named Entity Recognition (NER) models and scripts used to extract information from the medical texts.

## Table of Contents
1. [Connection](#connection)
2. [Structure](#structure)

## Connection

The connection to the NER models is managed through the `config.ini` file located in `NER/src/`.

```ini
[info]
# Input data to run mer_entities and mer_entities_batch files. 
# Mantainer: 
# Version 1.0
# Date: May, 23rd 2022

[SAMPLE]
splitedSize: 1000


[PATH]
path_to_entities_json: /opt/airflow/dags/NER/data/entities/

path_to_info: /opt/airflow/dags/NER/data/info_process.txt
path2blacklist: /opt/airflow/dags/NER/data/blacklists/blacklist.txt

path2drugbank: /opt/airflow/dags/NER/src/ner_drugbank.py

[ONTO]

active_lexicons: doid, chebi
# Update MER ontologies (yes: 1 | no: 0)
update: 0

[VOCABULARY]
zip_url = https://go.drugbank.com/releases/5-1-13/downloads/all-drugbank-vocabulary
output_folder = /opt/airflow/dags/NER/data
```
- `splitedSize`: Size of the split for processing the entities.
- `path_to_entities_json`: Path to the folder where the entities JSON files are stored.
- `path_to_info`: Path to the file that contains information about the process.
- `path2blacklist`: Path to the blacklist file.
- `path2drugbank`: Path to the script that processes the DrugBank vocabulary.
- `active_lexicons`: List of active lexicons to be used in the NER process.
- `update`: Flag to indicate whether to update the MER ontologies (1 for yes, 0 for no).
- `zip_url`: URL to download the DrugBank vocabulary.
- `output_folder`: Path to the folder where the downloaded DrugBank vocabulary will be saved.

## Structure

