###############################################################################
#                                                                             #  
# @file: csv_converter.py                                                     #  
# @description: Converts CSV/TXT files to JSON format                         #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This module converts tabular data (CSV/TXT) into individual JSON records.   #
# Each row in the input file is transformed into a separate JSON file,        #
# allowing for more flexible processing in downstream tasks.                  #
#                                                                             #  
###############################################################################

import json
import pandas as pd
import os

def convert_file_to_json(input_file, output_directory, delimiter=",", skiprows=0):
    """
    Converts CSV or TXT files to individual JSON files.
    
    This function reads a tabular data file (CSV or TXT), processes each row,
    and converts it to a separate JSON file for more flexible handling.
    
    Args:
        input_file (str): Path to the input file.
        output_directory (str): Directory where JSON files will be saved.
        delimiter (str): Delimiter used in the file (default: ",").
        skiprows (int): Number of rows to skip at the beginning of the file (default: 0).
    
    Returns:
        str: Message indicating the number of JSON files created.
    
    Raises:
        Exception: If an error occurs during the conversion process.
    """
    try:
        # OBJECTIVE: Ensure output directory exists
        os.makedirs(output_directory, exist_ok=True)
        
        # OBJECTIVE: Read and parse the CSV/TXT file
        # Read the file with pandas using the specified delimiter and skip rows
        df = pd.read_csv(input_file, delimiter=delimiter, skiprows=skiprows)
        
        # OBJECTIVE: Normalize column names for consistency
        # Rename 'Ingredient' column to 'Proper Name' if it exists
        if 'Ingredient' in df.columns:
            df.rename(columns={'Ingredient': 'Proper Name'}, inplace=True)
        
        # OBJECTIVE: Clean the dataframe by removing empty data
        # Remove columns that are entirely empty
        df.dropna(axis=1, how="all", inplace=True)
        # Remove rows that are entirely empty
        df.dropna(how="all", inplace=True)
        # Replace NaN values with None for proper JSON conversion
        df = df.where(pd.notna(df), None)
        
        # OBJECTIVE: Convert dataframe to list of dictionaries for JSON serialization
        data = df.to_dict(orient="records")
        
        # OBJECTIVE: Create individual JSON files for each record
        file_count = 0
        for i, record in enumerate(data):
            # Generate output filename with sequential numbering
            output_file = os.path.join(output_directory, f"record_{i+1}.json")
            # Write the record to a JSON file with proper formatting
            with open(output_file, "w", encoding="utf-8") as json_file:
                json.dump(record, json_file, indent=4, ensure_ascii=False)
            file_count += 1
        
        # Return success message with count of created files
        return f"Conversion completed: {file_count} files created in {output_directory}"
    except Exception as e:
        # Propagate error with contextual information
        raise Exception(f"Error converting {input_file}: {str(e)}")