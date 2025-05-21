"""
This script analyzes a collection of JSON files containing drug entity data to:
1. Extract and track unique drug IDs (from ChEBI and DrugBank sources)
2. Identify files with invalid or missing drug IDs
3. Detect files with repeated drug IDs
4. Generate metadata reports and statistics about the dataset
5. Create lists of unique IDs, invalid files, and files with repeated IDs
The purpose is to perform quality control on the drug entity dataset
before further processing or importing into a database system.
"""
import os
import json
from collections import defaultdict

# Define file paths for input data and output reports
folder_path = "./data/entities/xml_results"      # Directory containing JSON drug entity files
metadata_file = "./data/metadata.txt"            # Output file for overall dataset statistics
unique_ids_file = "./data/unique_ids.txt"        # Output file to store all unique drug IDs
invalid_ids_file = "./data/invalid_ids.txt"      # Output file to list files with missing/invalid IDs
repeated_ids_file = "./data/repeated_ids.txt"    # Output file to list files with duplicate IDs

# Initialize data structures to track statistics and issues
ids = set()                      # Set to store all unique drug IDs across files
id_counts = defaultdict(int)     # Counter for each drug ID occurrence
id_to_files = defaultdict(set)   # Maps each drug ID to the files it appears in
total_files = 0                  # Counter for total JSON files processed
files_with_invalid_ids = 0       # Counter for files with missing/invalid drug IDs
files_with_repeated_ids = 0      # Counter for files containing duplicate drug IDs
invalid_files = []               # List to store filenames with invalid IDs
repeated_id_files = set()        # Set to store filenames with repeated IDs

# Iterate through all JSON files in the specified directory
for filename in os.listdir(folder_path):
    if filename.endswith(".json"):
        total_files += 1
        file_path = os.path.join(folder_path, filename)
        
        # Open and parse each JSON file
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            file_has_invalid_id = True  # Flag to track if the file has at least one valid ID
            file_ids = set()            # Set to track unique IDs within this specific file
            
            # Process each drug entry in the current file
            for drug in data.get("drug", []):
                # Extract drug IDs from different possible sources
                chebi_id = drug.get("chebi_id")
                drugbank_id = drug.get("drugbank_id")
                
                # Skip entries with no valid IDs
                if (chebi_id == "null" or not chebi_id) and (not drugbank_id or drugbank_id == "null"):
                    continue
                
                # Prioritize ChEBI ID, fallback to DrugBank ID
                drug_id = chebi_id if chebi_id and chebi_id != "null" else drugbank_id
                
                if drug_id:
                    file_has_invalid_id = False  # File has at least one valid ID
                    ids.add(drug_id)             # Add to global set of unique IDs
                    id_counts[drug_id] += 1      # Increment count for this ID
                    file_ids.add(drug_id)        # Add to set of IDs for this specific file
                    id_to_files[drug_id].add(filename)  # Track which file contains this ID
            
            # Track files with invalid/missing IDs
            if file_has_invalid_id:
                files_with_invalid_ids += 1
                invalid_files.append(filename)
            
            # Check if any drug ID appears more than once (repeated) in the dataset
            if any(id_counts[drug_id] > 1 for drug_id in file_ids):
                files_with_repeated_ids += 1
                repeated_id_files.add(filename)

# Write the list of unique drug IDs to a file
with open(unique_ids_file, "w", encoding="utf-8") as f:
    for drug_id in sorted(ids):
        # Extract the last part of the ID if it's a URL
        if drug_id.startswith("http://"):
            drug_id = drug_id.split("/")[-1]
        f.write(f"{drug_id}\n")

# Write the list of files with invalid IDs to a file
with open(invalid_ids_file, "w", encoding="utf-8") as f:
    for filename in invalid_files:
        f.write(f"{filename}\n")

# Write the list of files with repeated IDs to a file
with open(repeated_ids_file, "w", encoding="utf-8") as f:
    for filename in sorted(repeated_id_files):
        f.write(f"{filename}\n")

# Generate and write metadata summary statistics
with open(metadata_file, "w", encoding="utf-8") as f:
    f.write(f"\n")
    f.write(f"Total number of JSON files: {total_files}\n")
    f.write(f"Number of unique IDs found: {len(ids)}\n")
    f.write(f"Number of files with invalid IDs: {files_with_invalid_ids}\n")
    f.write(f"Number of files with repeated IDs: {files_with_repeated_ids}\n")
    f.write(f"\n")
    f.write(f"--------------------------------------------------------------------------\n")
    f.write(f"\n")
    f.write(f"Unique IDs have been saved to: {unique_ids_file}\n")
    f.write(f"Invalid IDs have been saved to: {invalid_ids_file}\n")
    f.write(f"File names with repeated IDs have been saved to: {repeated_ids_file}\n")

# Notify user that processing is complete
print("Processing complete. Please check the output files.")
