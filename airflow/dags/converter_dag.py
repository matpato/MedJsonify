from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.tasks import *

with DAG(
    'converter_dag',
    description='Convert different types of files to JSON and send to Neo4j',
    schedule_interval='@monthly',
    start_date=datetime.now(),
    catchup=False,
) as dag:
    
    task_convert_files_to_json = PythonOperator(
        task_id='convert_files_to_json',
        python_callable=convert_files_to_json_task,
    )

    task_convert_files_to_json 
