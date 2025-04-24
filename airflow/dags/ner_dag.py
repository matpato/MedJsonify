from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.tasks import ner_process_task


with DAG(
    'ner_dag',
    description='NER process',
    schedule_interval='@monthly',
    start_date=datetime.now(),
    catchup=False,
) as dag:
    
    task_ner = PythonOperator(
        task_id='ner',
        python_callable=ner_process_task,
    )

    task_ner
