# Upload

This module provides functionality to extract files from a URL, extract XML files from a ZIP file and finally extract only the files that we want to work with.

## Table of Contents
1. [Configuration](#configuration)
2. [Structure](#structure)

## Configuration

The directories to extract and upload files are managed through the `upload.ini` file. Below is an example configuration:

```ini
[general]
downloads_dir=~/Downloads
selected_url=purplebook, dailymed

[urls]
dailymed=https://dailymed.nlm.nih.gov/dailymed/spl-resources-all-drug-labels.cfm
orangebook=https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files
purplebook=https://purplebooksearch.fda.gov/files/2023/purplebook-search-january-data-download.csv

[dest_directory]
dailymed=/opt/airflow/dags/jsonify/src/types/xml_files
orangebook=/opt/airflow/dags/jsonify/src/types/txt_files
purplebook=/opt/airflow/dags/jsonify/src/types/csv_files
```

**Configuration Parameters:** 
- `downloads_dir`: Directory where the ZIP file will be downloaded.
- `selected_url`: Selected URLs to download the ZIP file (it can be one or more).
- `urls`: URLs to download the ZIP file.
- `dest_directory`: Destination directory to extract the files.

## Structure

```bash
upload/
├── upload.ini
├── download_from_url.py
├── unzip_directories.py
├── extract_files.py 
└── upload_loader.py
```

The project is organized as follows:º
- `upload.ini`: Configuration file.
- `download_from_url.py`: Downloads the ZIP file from the selected URL.
- `unzip_directories.py`: Extracts the ZIP file.
- `extract_files.py`: Extracts the files that we want to work with.
- `upload_loader.py`: The script that extracts the `upload.ini` information. If you want to change something in the configuration file, you need to add or modify here too.
