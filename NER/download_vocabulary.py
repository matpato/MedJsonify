"""
This function handles downloading a ZIP file from a URL, extracting all its contents to a specified 
folder, and then specifically looking for CSV files within that archive. The function returns the path 
to the first CSV file it finds or None if no CSV is found or if the download fails.
"""
import requests
import zipfile
import io
import os

def download_and_extract_zip(url, output_folder):
    """
    Downloads a ZIP file from a given URL and extracts its contents to the specified folder.
    Specifically looks for CSV files within the ZIP archive.
    
    Args:
        url (str): The URL of the ZIP file to download
        output_folder (str): The directory path where the ZIP contents will be extracted
        
    Returns:
        str or None: Path to the extracted CSV file if found, None otherwise
    """
    # Send HTTP GET request to download the ZIP file
    response = requests.get(url)
    
    # Check if the download was successful (HTTP status code 200)
    if response.status_code == 200:
        # Create a ZIP file object from the downloaded content in memory
        # BytesIO converts the binary content to a file-like object
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # Extract all files from the ZIP archive to the specified folder
            z.extractall(output_folder)
            print(f"Files extracted from: {output_folder}")
            
            # Iterate through all files in the ZIP archive
            # to find any CSV files that may be present
            for file_name in z.namelist():
                if file_name.endswith('.csv'):
                    print(f"CSV file found: {file_name}")
                    # Return the full path to the extracted CSV file
                    return os.path.join(output_folder, file_name)
            
            # If no CSV files were found in the ZIP
            print("No CSV file found in ZIP.")
            return None
    else:
        # Handle failed download (non-200 HTTP status code)
        print(f"Download failed. Status code: {response.status_code}")
        return None