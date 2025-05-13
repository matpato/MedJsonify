"""
This script automates the downloading of pharmaceutical database files from multiple sources:
1. DailyMed - For FDA-approved drug labeling information
2. Purple Book - For FDA-licensed biological products
3. Orange Book - For FDA-approved drug products
The script identifies the correct download links, handles different download methods for each source,
maintains a record of downloaded files, and manages error cases.
Its purpose is to keep local pharmaceutical databases up-to-date with minimal manual intervention.
"""
import os
import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
from datetime import datetime
from upload.upload_loader import UploadLoader

# Load configuration from the UploadLoader
config = UploadLoader()
downloads_dir = config.get_downloads_dir()           # Directory where files will be downloaded
selected_directories = config.get_selected_directories()  # List of pharmaceutical database names to download
urls = config.get_urls()                             # Corresponding URLs for each database

def get_previous_month_url(base_url):
    """
    Calculates the URL for the previous month's data file for time-sensitive sources.
    
    Args:
        base_url (str): Template URL containing placeholders for year and month
        
    Returns:
        tuple: (modified_url, year, month) for the previous month's data
    """
    today = datetime.today()
    year = today.year
    month = today.month - 1  # Previous month
    
    if month == 0:  # If January, adjust to December of previous year
        month = 12
        year -= 1
    
    # Replace placeholders in URL with calculated values
    formatted_url = base_url.replace("2023", str(year)).replace("january", datetime(year, month, 1).strftime('%B').lower())
    return formatted_url, year, month

def download_file_from_url(url, dest_path):
    """
    Downloads a file from a specified URL to a local destination path.
    Uses a custom user agent to avoid blocking and handles the file in chunks.
    
    Args:
        url (str): URL of the file to download
        dest_path (str): Local path where the file will be saved
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f'Download finished with success: {dest_path}')
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
        raise
    except Exception as err:
        print(f'Other error occurred: {err}')
        raise


def process_dailymed(url, downloads_dir):
    """
    Processes DailyMed database download.
    DailyMed requires scraping the page to find the ZIP file link before downloading.
    
    Args:
        url (str): URL of the DailyMed download page
        downloads_dir (str): Directory to save the downloaded file
    """
    response = requests.get(url)
    response.raise_for_status()  

    # Parse the HTML page to find the ZIP file link
    soup = BeautifulSoup(response.text, 'html.parser')

    zip_link = None
    for a_tag in soup.find_all('a', href=True):
        if a_tag['href'].endswith('.zip'):
            zip_link = a_tag['href']
            break

    if zip_link is None:
        raise ValueError("No ZIP file link found on the page.")

    # Ensure the link is a complete URL
    if not zip_link.startswith('http'):
        zip_url = f'https://dailymed.nlm.nih.gov{zip_link}'
    else:
        zip_url = zip_link

    # Prepare file paths and record the filename
    zip_filename = os.path.basename(zip_link)
    zip_filepath = os.path.join(downloads_dir, zip_filename)

    with open(os.path.join(downloads_dir, 'filename.txt'), 'a') as f:
        f.write(zip_filename + "\n")

    # Download the file
    download_file_from_url(zip_url, zip_filepath)

def process_purplebook(url, downloads_dir):
    """
    Processes Purple Book database download.
    Purple Book requires calculating the previous month's URL before downloading.
    
    Args:
        url (str): Template URL for Purple Book data
        downloads_dir (str): Directory to save the downloaded file
    """
    # Get URL for the previous month's data
    updated_url, year, month = get_previous_month_url(url)
    print(f'PurpleBook: Downloading from {updated_url}')
    
    # Prepare file paths
    csv_filename = os.path.basename(updated_url)
    csv_filepath = os.path.join(downloads_dir, csv_filename)
    
    try:
        # Download the file and record its name
        download_file_from_url(updated_url, csv_filepath)
        if os.path.exists(csv_filepath):
            with open(os.path.join(downloads_dir, 'filename.txt'), 'a') as f:
                f.write(csv_filename + "\n")
            print(f'Filename written to filename.txt: {csv_filename}')
        else:
            print(f'Error: Downloaded file not found at {csv_filepath}')
    except Exception as e:
        print(f'Error processing PurpleBook: {e}')

def process_orangebook(url, downloads_dir):
    """
    Download the Orange Book ZIP file directly from the given URL.
    Orange Book provides a direct download link for its data.

    Args:
        url (str): Direct URL to the Orange Book ZIP file.
        downloads_dir (str): Directory to save the downloaded file.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # Set a filename since the URL doesn't contain a proper one
        zip_filename = 'orangebook.zip'
        zip_filepath = os.path.join(downloads_dir, zip_filename)

        # Download the file
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()

        with open(zip_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Record the filename
        with open(os.path.join(downloads_dir, 'filename.txt'), 'a') as f:
            f.write(zip_filename + "\n")

        print(f'Orange Book file downloaded successfully: {zip_filepath}')

    except Exception as e:
        print(f'Error processing Orange Book: {e}')


# Create downloads directory if it doesn't exist
os.makedirs(downloads_dir, exist_ok=True)

# Initialize/clear the filename tracking file
open(os.path.join(downloads_dir, 'filename.txt'), 'w').close()

# Process each selected database
for i in range(len(selected_directories)):
    name = selected_directories[i]
    url = urls[i]
    try:
        # Route to the appropriate processing function based on database name
        if 'dailymed' in name.lower():
            process_dailymed(url, downloads_dir)
        elif 'purplebook' in name.lower():
            process_purplebook(url, downloads_dir)
        elif 'orangebook' in name.lower():
            process_orangebook(url, downloads_dir)
        else:
            print(f"URL not supported: {url}")
    except ValueError as ve:
        print(f"An error occurred: {ve}")
    except Exception as ex:
        print(f"An unexpected error occurred: {ex}")