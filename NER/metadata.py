import os
import json
from collections import defaultdict

folder_path = "./data/entities/xml_results"
metadata_file = "./data/metadata.txt"
unique_ids_file = "./data/unique_ids.txt"
invalid_ids_file = "./data/invalid_ids.txt"
repeated_ids_file = "./data/repeated_ids.txt"

ids = set()
id_counts = defaultdict(int) 
id_to_files = defaultdict(set)  

total_files = 0
files_with_invalid_ids = 0
files_with_repeated_ids = 0
invalid_files = []
repeated_id_files = set()

for filename in os.listdir(folder_path):
    if filename.endswith(".json"):
        total_files += 1
        file_path = os.path.join(folder_path, filename)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            file_has_invalid_id = True
            file_ids = set() 

            for drug in data.get("drug", []):
                chebi_id = drug.get("chebi_id")
                drugbank_id = drug.get("drugbank_id")

                if (chebi_id == "null" or not chebi_id) and (not drugbank_id or drugbank_id == "null"):
                    continue  

                drug_id = chebi_id if chebi_id and chebi_id != "null" else drugbank_id
                if drug_id:
                    file_has_invalid_id = False 
                    ids.add(drug_id)
                    id_counts[drug_id] += 1
                    file_ids.add(drug_id)
                    id_to_files[drug_id].add(filename)

            if file_has_invalid_id:
                files_with_invalid_ids += 1
                invalid_files.append(filename)

            if any(id_counts[drug_id] > 1 for drug_id in file_ids):
                files_with_repeated_ids += 1
                repeated_id_files.add(filename)

with open(unique_ids_file, "w", encoding="utf-8") as f:
    for drug_id in sorted(ids):
        if drug_id.startswith("http://"):
            drug_id = drug_id.split("/")[-1]
        f.write(f"{drug_id}\n")

with open(invalid_ids_file, "w", encoding="utf-8") as f:
    for filename in invalid_files:
        f.write(f"{filename}\n")

with open(repeated_ids_file, "w", encoding="utf-8") as f:
    for filename in sorted(repeated_id_files):
        f.write(f"{filename}\n")

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

print("Processing complete. Please check the output files.")
