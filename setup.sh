#!/bin/bash

###############################################################################
# MedJsonify Setup Script
# 
# This script helps you set up all the missing configuration files
# and verify your directory structure.
###############################################################################

set -e  # Exit on error

echo "======================================================================"
echo "MedJsonify Configuration Setup"
echo "======================================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}ERROR: docker-compose.yml not found!${NC}"
    echo "Please run this script from your medjsonify root directory"
    exit 1
fi

echo -e "${GREEN}✓${NC} Found docker-compose.yml"
echo ""

# Function to create a file with content
create_config_file() {
    local file_path=$1
    local file_content=$2
    
    # Create directory if it doesn't exist
    mkdir -p "$(dirname "$file_path")"
    
    if [ -f "$file_path" ]; then
        echo -e "${YELLOW}⚠${NC}  File exists: $file_path (skipping)"
    else
        echo "$file_content" > "$file_path"
        echo -e "${GREEN}✓${NC} Created: $file_path"
    fi
}

echo "Creating configuration files..."
echo ""

# 1. Create upload/upload.ini
read -r -d '' UPLOAD_INI << 'EOF' || true
[general]
# Base directory for downloaded files
downloads_dir=/opt/airflow/dags/upload/downloads
# Selected data sources (comma-separated)
selected_url=purplebook, dailymed, orangebook

[urls]
# Data source URLs for download
dailymed=https://dailymed.nlm.nih.gov/dailymed/spl-resources-all-drug-labels.cfm
orangebook=https://www.fda.gov/media/76860/download?attachment
purplebook=https://purplebooksearch.fda.gov/files/2023/purplebook-search-january-data-download.csv

[dest_directory]
dailymed=/opt/airflow/dags/jsonify/src/types/xml_files
orangebook=/opt/airflow/dags/jsonify/src/types/txt_files
purplebook=/opt/airflow/dags/jsonify/src/types/csv_files

[source_paths]
# Paths within extracted archives (relative to base directory)
dailymed=prescription
orangebook=orangebook
purplebook=.

[file_patterns]
# File patterns to extract from each source
dailymed=*.xml
orangebook=products.txt
purplebook=*.csv
EOF

create_config_file "upload/upload.ini" "$UPLOAD_INI"

# 2. Create jsonify/jsonify.ini
read -r -d '' JSONIFY_INI << 'EOF' || true
[folders]
# Base folder for input files (before conversion)
base_input_folder = /opt/airflow/dags/jsonify/input

# Base folder for output JSON files (after conversion)
base_output_folder = /opt/airflow/dags/jsonify/output

[conversion]
# Conversion settings
preserve_formatting = true
include_metadata = true
EOF

create_config_file "jsonify/jsonify.ini" "$JSONIFY_INI"

# 3. Create upload/upload_loader.py
read -r -d '' UPLOAD_LOADER << 'EOF' || true
"""
Upload Configuration Loader Module
"""

import configparser
import os

class UploadLoader:
    def __init__(self, config_file='/opt/airflow/dags/upload/upload.ini'):
        self.config = configparser.ConfigParser()
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        self.config.read(config_file)
    
    def get_downloads_dir(self):
        return self.config['general']['downloads_dir']
    
    def get_selected_directories(self):
        selected_url = self.config['general']['selected_url']
        return [i.strip().strip("'").strip('"') for i in selected_url.split(',')]
    
    def get_dest_directories(self):
        selected = self.get_selected_directories()
        return [self.config['dest_directory'][d] for d in selected]
    
    def get_source_paths(self):
        selected = self.get_selected_directories()
        return [self.config['source_paths'][d] for d in selected]
    
    def get_file_patterns(self):
        selected = self.get_selected_directories()
        return [self.config['file_patterns'][d] for d in selected]
    
    def get_urls(self):
        selected = self.get_selected_directories()
        return [self.config['urls'][d] for d in selected]
EOF

create_config_file "upload/upload_loader.py" "$UPLOAD_LOADER"

echo ""
echo "======================================================================"
echo "Checking directory structure..."
echo "======================================================================"
echo ""

# Check for required directories
REQUIRED_DIRS=(
    "airflow/dags"
    "airflow/dags/utils"
    "NER"
    "NER/ontologies/data"
    "NER/ontologies/scripts"
    "jsonify"
    "upload"
    "database"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} Directory exists: $dir"
    else
        echo -e "${RED}✗${NC} Missing directory: $dir"
        mkdir -p "$dir"
        echo -e "${GREEN}✓${NC} Created directory: $dir"
    fi
done

echo ""
echo "======================================================================"
echo "Verifying configuration files..."
echo "======================================================================"
echo ""

# Check for required config files
REQUIRED_FILES=(
    "upload/upload.ini"
    "jsonify/jsonify.ini"
    "NER/bioner.ini"
    "database/neo4j.ini"
    "airflow/dags/airflow.cfg"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} Config file exists: $file"
    else
        echo -e "${YELLOW}⚠${NC}  Missing config file: $file"
    fi
done

echo ""
echo "======================================================================"
echo "Checking Python files..."
echo "======================================================================"
echo ""

REQUIRED_PYTHON=(
    "upload/upload_loader.py"
    "airflow/dags/utils/config.py"
    "airflow/dags/utils/tasks.py"
)

for file in "${REQUIRED_PYTHON[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} Python file exists: $file"
    else
        echo -e "${YELLOW}⚠${NC}  Missing Python file: $file"
    fi
done

echo ""
echo "======================================================================"
echo "Next Steps"
echo "======================================================================"
echo ""
echo "1. Review the created configuration files and update with your values:"
echo "   - upload/upload.ini (add your actual data source URLs)"
echo "   - jsonify/jsonify.ini (verify paths)"
echo ""
echo "2. Update airflow/dags/utils/config.py to use correct paths:"
echo "   Change: /app/upload/upload.ini"
echo "   To:     /opt/airflow/dags/upload/upload.ini"
echo "   (Do this for all config file paths)"
echo ""
echo "3. Start your Docker containers:"
echo "   docker-compose down -v"
echo "   docker-compose up --build -d"
echo ""
echo "4. Check Airflow logs:"
echo "   docker-compose logs -f airflow"
echo ""
echo "5. Access Airflow UI:"
echo "   http://localhost:8080"
echo "   Username: admin"
echo "   Password: admin"
echo ""
echo -e "${GREEN}Setup complete!${NC}"