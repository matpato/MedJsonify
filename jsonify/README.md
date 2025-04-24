# Converter

This package provides functionality to convert different types of files to JSON format.

## Table of Contents
1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Structure](#structure)

## Installation

## Configuration
The configuration for this module is managed through the `config.ini` file. Below is an example configuration:
```ini
[general]
conversion_method=python
file_type=xml, csv

[folders]
base_input_folder=/opt/airflow/dags/jsonify/src/types
base_output_folder=/opt/airflow/dags/jsonify/src/json

[log_files]
log_file=/opt/airflow/dags/jsonify/src/info/missing_fields_log.txt
unconverted_file=/opt/airflow/dags/jsonify/src/info/unconverted_files.txt
processed_medications_file=/opt/airflow/dags/jsonify/src/info/drugs.txt
processing_summary_file=/opt/airflow/dags/jsonify/src/info/summary.txt
```

**Configuration Parameters:**
- `conversion_method`: Specifies the method to use for xml **(only)** conversion. Options are "python" or "xslt".
- `file_type`: Specifies the file types to convert. Options are "csv", "xml".
- `base_input_folder`: Specifies the base directory where the input files are located.
- `base_output_folder`: Specifies the base directory where the output files will be saved.
- `log_file`: Specifies the file path to save the log of missing fields.
- `unconverted_file`: Specifies the file path to save the list of unconverted files.
- `processed_medications_file`: Specifies the file path to save the list of processed drugs.
- `processing_summary_file`: Specifies the file path to save the summary of the processing.

## Structure
The project is organized as follows:

```bash
jsonify
├── config.ini
├── conversion_xslt.xslt
├── setup.py
└── src
    ├── converter/
    ├── info/
    ├── json/
    ├── types/
    ├── config_loader.py
    └── main.py
```

- `config.ini`: Configuration file for the converter.
- `conversion_xslt.xslt`: XSLT file for xml conversion.
- `setup.py`: Setup file for the package.
- `src/converter/`: Contains the conversion logic for different file types.
- `src/info/`: Contains the log files for missing fields, unconverted files, and processed medications.
- `src/json/`: Contains the converted JSON files.
- `src/types/`: Contains the input files to be converted.
- `src/config_loader.py`: Module that connects `.ini` file with the converter.
- `src/main.py`: Main module to execute the converter.

