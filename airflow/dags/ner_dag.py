from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.tasks import ner_process_task, preprocess_json_task


with DAG(
    'ner_dag',
    description='NER process',
    schedule_interval='@monthly',
    start_date=datetime.now(),
    catchup=False,
) as dag:
    task_preprocess_json = PythonOperator(
        task_id='preprocess_json',
        python_callable=preprocess_json_task,
    )
    task_ner_process = PythonOperator(
        task_id='ner_process',
        python_callable=ner_process_task,
    )

    task_preprocess_json >> task_ner_process
