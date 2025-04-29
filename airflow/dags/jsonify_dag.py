from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.tasks import *

with DAG(
    'jsonify_dag',
    description='Convert different types of files to JSON and send to Neo4j',
    schedule_interval='@monthly',
    start_date=datetime.now(),
    catchup=False,
) as dag:
    
    task_download_from_url = PythonOperator(
        task_id='download_from_url',
        python_callable=download_zip_task,
    )

    task_unzip_directories = PythonOperator(
        task_id='unzip_directories',
        python_callable=unzip_task,
    )

    task_extract_files = PythonOperator(
        task_id='extract_files',
        python_callable=extract_xml_files_task,
    )

    task_convert_files_to_json = PythonOperator(
        task_id='convert_files_to_json',
        python_callable=convert_files_to_json_task,
    )
    
    task_download_vocabulary = PythonOperator(
        task_id='download_vocabulary',
        python_callable=download_vocabulary_task,
    )

    task_preprocess_json = PythonOperator(
        task_id='preprocess_json',
        python_callable=preprocess_json_task,
    )
    
    task_ner_process = PythonOperator(
        task_id='ner_process',
        python_callable=ner_process_task,
    )

    task_download_from_url >> task_unzip_directories >> task_extract_files >> task_convert_files_to_json >> task_download_vocabulary >> task_preprocess_json >> task_ner_process 
