""" 
This script is performing a data validation task, checking which entities from your expected list 
(unique_ids.txt) were successfully inserted into Neo4j by scanning the processed JSON files. 
"""
import json
import os

# Load all unique IDs from the metadata file
# These IDs represent all entities that should be processed
with open('./data/unique_ids.txt', 'r') as f:
    unique_ids = set(line.strip() for line in f)

# Initialize an empty set to track which IDs were actually inserted into Neo4j
# This will be populated by scanning the processed JSON files
inserted_ids = set()

# Define the directory path containing the processed JSON files that were sent to Neo4j
folder_path = "./data/entities/xml_results"

# Iterate through each JSON file in the directory
for filename in os.listdir(folder_path):
    # Process only JSON files, skip other file types
    if filename.endswith(".json"):
        file_path = os.path.join(folder_path, filename)
        
        # Open and parse each JSON file
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # Extract drug IDs from each drug entry in the JSON data
            for drug_entry in data.get("drug", []):
                # Try to extract drug ID from different possible sources:
                # 1. ChEBI ID (if present)
                # 2. DrugBank ID (if present)
                # Take only the last part of the ID (after the last slash)
                drug_id = (drug_entry.get("chebi_id", "").split("/")[-1] if drug_entry.get("chebi_id") else
                           drug_entry.get("drugbank_id", "").split("/")[-1] if drug_entry.get("drugbank_id") else
                           None)
                
                # If a valid drug ID was found, add it to the set of inserted IDs
                if drug_id:
                    inserted_ids.add(drug_id)

# Calculate the difference between all unique IDs and those that were actually inserted
# This identifies IDs that were expected to be processed but are missing from the Neo4j database
lost_ids = unique_ids - inserted_ids

# Print summary statistics for analysis and debugging
print(f"Total unique IDs: {len(unique_ids)}")           # Total number of IDs that should have been processed
print(f"Total inserted IDs: {len(inserted_ids)}")       # Total number of IDs actually inserted into Neo4j
print(f"Lost IDs: {lost_ids}")                          # The specific IDs that were not inserted
print(f"Number of lost IDs: {len(lost_ids)}")           # The count of missing IDs