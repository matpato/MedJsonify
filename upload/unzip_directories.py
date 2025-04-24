import zipfile
import os
from tqdm import tqdm
from upload.upload_loader import UploadLoader

config = UploadLoader()
downloads_dir = config.get_downloads_dir()

# -------------------------------------------------------------------------------------------

def unzip_file(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

# -------------------------------------------------------------------------------------------

def unzip_all_in_directory(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.zip'):
                zip_path = os.path.join(root, file)
                extract_to = os.path.splitext(zip_path)[0]
                unzip_file(zip_path, extract_to)
                unzip_all_in_directory(extract_to)

# -------------------------------------------------------------------------------------------

def unzip_file_with_progress(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        for file in tqdm(file_list, desc="Decompressing", unit="file"):
            zip_ref.extract(file, extract_to)

# -------------------------------------------------------------------------------------------

with open(os.path.join(downloads_dir, 'filename.txt'), 'r') as f:
    zip_filenames = f.readlines()
    for i in range(len(zip_filenames)):
        zip_filenames[i] = zip_filenames[i].strip('\n')

zip_file_paths = [os.path.join(downloads_dir, zip_filename) for zip_filename in zip_filenames]

# Verifica se o ficheiro tem a extensão .zip
for zip_file_path in zip_file_paths:
    if zip_file_path.endswith('.zip'):
        extract_to = os.path.splitext(zip_file_path)[0]
        unzip_file_with_progress(zip_file_path, extract_to)
        unzip_all_in_directory(extract_to)
        
        os.remove(zip_file_path)
    else:
        print(f"O ficheiro {zip_file_path} não é um ficheiro .zip.")
