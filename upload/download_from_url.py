import os
import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
from datetime import datetime
from upload.upload_loader import UploadLoader

config = UploadLoader()
downloads_dir = config.get_downloads_dir()
selected_directories = config.get_selected_directories()
urls = config.get_urls()

# -------------------------------------------------------------------------------------------

def get_previous_month_url(base_url):
    today = datetime.today()
    year = today.year
    month = today.month - 1  # Mês anterior
    
    if month == 0:  # Se for janeiro, ajustamos para dezembro do ano anterior
        month = 12
        year -= 1
    
    formatted_url = base_url.replace("2023", str(year)).replace("january", datetime(year, month, 1).strftime('%B').lower())
    return formatted_url, year, month

# -------------------------------------------------------------------------------------------

def download_file_from_url(url, dest_path):
    try:
        response = requests.get(url, stream=True)
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

# -------------------------------------------------------------------------------------------

def process_dailymed(url, downloads_dir):
    response = requests.get(url)
    response.raise_for_status()  

    soup = BeautifulSoup(response.text, 'html.parser')

    zip_link = None
    for a_tag in soup.find_all('a', href=True):
        if a_tag['href'].endswith('.zip'):
            zip_link = a_tag['href']
            break

    if zip_link is None:
        raise ValueError("No ZIP file link found on the page.")

    if not zip_link.startswith('http'):
        zip_url = f'https://dailymed.nlm.nih.gov{zip_link}'
    else:
        zip_url = zip_link

    zip_filename = os.path.basename(zip_link)
    zip_filepath = os.path.join(downloads_dir, zip_filename)

    with open(os.path.join(downloads_dir, 'filename.txt'), 'a') as f:
        f.write(zip_filename + "\n")

    download_file_from_url(zip_url, zip_filepath)

# -------------------------------------------------------------------------------------------

def process_purplebook(url, downloads_dir):
    updated_url, year, month = get_previous_month_url(url)
    print(f'PurpleBook: Downloading from {updated_url}')
    csv_filename = os.path.basename(updated_url)
    csv_filepath = os.path.join(downloads_dir, csv_filename)
    
    try:
        download_file_from_url(updated_url, csv_filepath)
        if os.path.exists(csv_filepath):
            with open(os.path.join(downloads_dir, 'filename.txt'), 'a') as f:
                f.write(csv_filename + "\n")
            print(f'Filename written to filename.txt: {csv_filename}')
        else:
            print(f'Error: Downloaded file not found at {csv_filepath}')
    except Exception as e:
        print(f'Error processing PurpleBook: {e}')

# -------------------------------------------------------------------------------------------

os.makedirs(downloads_dir, exist_ok=True)
open(os.path.join(downloads_dir, 'filename.txt'), 'w').close()

for i in range(len(selected_directories)):
    name = selected_directories[i]
    url = urls[i]
    try:
        if 'dailymed' in name.lower():
            process_dailymed(url, downloads_dir)
        elif 'purplebook' in name.lower():
            process_purplebook(url, downloads_dir)
        else:
            print(f"URL not supported: {url}")
    except ValueError as ve:
        print(f"An error occurred: {ve}")
    except Exception as ex:
        print(f"An unexpected error occurred: {ex}")
