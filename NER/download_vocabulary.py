import requests
import zipfile
import io
import os


def download_and_extract_zip(url, output_folder):
    response = requests.get(url)
    
    if response.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # Lista os arquivos no ZIP
            z.extractall(output_folder)
            print(f"Arquivos extraídos em: {output_folder}")
            
            # Encontra o arquivo CSV (ajuste se o nome for diferente)
            for file_name in z.namelist():
                if file_name.endswith('.csv'):
                    print(f"Arquivo CSV encontrado: {file_name}")
                    return os.path.join(output_folder, file_name)
            
            print("Nenhum arquivo CSV encontrado no ZIP.")
            return None
    else:
        print(f"Falha no download. Status code: {response.status_code}")
        return None
