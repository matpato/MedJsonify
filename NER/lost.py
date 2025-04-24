import json
import os

# Carrega todos os IDs do metadata.txt
with open('./data/unique_ids.txt', 'r') as f:
    unique_ids = set(line.strip() for line in f)

# Carregar os IDs que realmente foram inseridos no Neo4j
inserted_ids = set()

# Pasta com os JSONs originais
folder_path = "./data/entities/xml_results"

for filename in os.listdir(folder_path):
    if filename.endswith(".json"):
        file_path = os.path.join(folder_path, filename)
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            for drug_entry in data.get("drug", []):
                drug_id = (drug_entry.get("chebi_id", "").split("/")[-1] if drug_entry.get("chebi_id") else 
                           drug_entry.get("drugbank_id", "").split("/")[-1] if drug_entry.get("drugbank_id") else 
                           None)
                
                if drug_id:
                    inserted_ids.add(drug_id)

# Identificar os IDs que estão em unique_ids mas não em inserted_ids
lost_ids = unique_ids - inserted_ids

print(f"Total de unique IDs: {len(unique_ids)}")
print(f"Total de IDs inseridos: {len(inserted_ids)}")
print(f"IDs perdidos: {lost_ids}")
print(f"Número de IDs perdidos: {len(lost_ids)}")