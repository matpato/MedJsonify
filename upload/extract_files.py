import os
import shutil
from tqdm import tqdm
from upload.upload_loader import UploadLoader

config = UploadLoader()
downloads_dir = config.get_downloads_dir()
selected_directories = config.get_selected_directories()
dest_directories = config.get_dest_directories()

# -------------------------------------------------------------------------------------------

def copy_xml_files(src_directory, dest_directory):
    if not os.path.exists(dest_directory):
        try:
            os.makedirs(dest_directory)
        except PermissionError:
            print(f"Permissões insuficientes para criar a diretoria: {dest_directory}")
            return
    
    xml_files = []
    for root, _, files in os.walk(src_directory):
        for file in files:
            if file.endswith('.xml'):
                xml_files.append(os.path.join(root, file))
    
    for src_file in tqdm(xml_files, desc="Copiando arquivos XML", unit="arquivo"):
        shutil.copy(src_file, dest_directory)

# -------------------------------------------------------------------------------------------

with open(os.path.join(downloads_dir, 'filename.txt'), 'r') as f:
    file_filenames = f.readlines()
    for i in range(len(file_filenames)):
        file_filenames[i] = file_filenames[i].strip('\n')

for i in range(len(file_filenames)):
    if selected_directories[i] == 'dailymed':
        src_directory = os.path.expanduser(f'{downloads_dir}/{os.path.splitext(file_filenames[i])[0]}/prescription')
        copy_xml_files(src_directory, dest_directories[i])
    elif selected_directories[i] == 'purplebook':
        src_file = os.path.join(downloads_dir, file_filenames[i])
        shutil.copy(src_file, dest_directories[i])
    elif selected_directories[i] == 'orangebook':
        # Copiar apenas o ficheiro products.txt
        src_file = os.path.join(downloads_dir, 'orangebook', 'products.txt')
        dest_directory = dest_directories[i]
        if not os.path.exists(dest_directory):
            os.makedirs(dest_directory)
        shutil.copy(src_file, dest_directory)
        print(f"Copiado {src_file} para {dest_directory}")