import json
import pandas as pd
import os

def convert_csv_to_json(input_file, output_directory):
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)
        
        # Read CSV file, skipping the first 3 rows
        df = pd.read_csv(input_file, skiprows=3)
        
        # Clean up the dataframe
        df.dropna(axis=1, how="all", inplace=True)
        df.dropna(how="all", inplace=True)
        df = df.where(pd.notna(df), None)
        
        # Convert to list of dictionaries
        data = df.to_dict(orient="records")
        
        # Create individual JSON files
        file_count = 0
        for i, record in enumerate(data):
            output_file = os.path.join(output_directory, f"record_{i+1}.json")
            with open(output_file, "w", encoding="utf-8") as json_file:
                json.dump(record, json_file, indent=4, ensure_ascii=False)
            file_count += 1
        
        return f"Conversão concluída: {file_count} arquivos criados em {output_directory}"
    except Exception as e:
        raise Exception(f"Erro ao converter {input_file}: {str(e)}")