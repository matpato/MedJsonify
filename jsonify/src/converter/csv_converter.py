import json
import pandas as pd
import os

def convert_file_to_json(input_file, output_directory, delimiter=",", skiprows=0):
    """
    Converte arquivos CSV ou TXT para JSON.

    Args:
        input_file (str): Caminho do arquivo de entrada.
        output_directory (str): Diretório onde os arquivos JSON serão salvos.
        delimiter (str): Delimitador usado no arquivo (padrão: ",").
        skiprows (int): Número de linhas a ignorar no início do arquivo (padrão: 0).

    Returns:
        str: Mensagem indicando o número de arquivos JSON criados.
    """
    try:
        # Cria o diretório de saída, se não existir
        os.makedirs(output_directory, exist_ok=True)
        
        # Lê o arquivo com o delimitador especificado
        df = pd.read_csv(input_file, delimiter=delimiter, skiprows=skiprows)
        
        # Renomeia a coluna 'Ingredient' para 'Proper Name', se existir
        if 'Ingredient' in df.columns:
            df.rename(columns={'Ingredient': 'Proper Name'}, inplace=True)
        
        # Limpa o dataframe
        df.dropna(axis=1, how="all", inplace=True)
        df.dropna(how="all", inplace=True)
        df = df.where(pd.notna(df), None)
        
        # Converte para uma lista de dicionários
        data = df.to_dict(orient="records")
        
        # Cria arquivos JSON individuais
        file_count = 0
        for i, record in enumerate(data):
            output_file = os.path.join(output_directory, f"record_{i+1}.json")
            with open(output_file, "w", encoding="utf-8") as json_file:
                json.dump(record, json_file, indent=4, ensure_ascii=False)
            file_count += 1
        
        return f"Conversão concluída: {file_count} arquivos criados em {output_directory}"
    except Exception as e:
        raise Exception(f"Erro ao converter {input_file}: {str(e)}")