###############################################################################
#                                                                             #  
# @file: ner_dag.py                                                           #  
# @description: Airflow DAG for Named Entity Recognition processing           #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This module defines an Airflow DAG (Directed Acyclic Graph) that runs       #
# Named Entity Recognition (NER) processing on preprocessed biomedical data.  #
# The DAG is scheduled to run monthly and focuses solely on the NER task,     #
# assuming preprocessing has been handled separately or previously.           #
#                                                                             #  
###############################################################################

from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.tasks import ner_process_task, preprocess_json_task
from airflow.models.variable import Variable

# OBJECTIVE: Define the Named Entity Recognition (NER) DAG
# Create a monthly scheduled DAG for NER processing
with DAG(
    # DAG identifier used in the Airflow UI
    '3_ner_dag',
    # Description of the DAG's purpose
    description='Named Entity Recognition process for biomedical entities extraction',
    # Schedule the DAG to run monthly
    schedule_interval='@monthly',
    # Set start date to current time (will run on next schedule after this time)
    start_date=datetime.now(),
    # Don't run for periods that were missed if the scheduler was down
    catchup=False,
) as dag:
    
    # Obtenha o email da Variável do Airflow
    # Use Variable.get() para ler do banco de dados do Airflow
    email_string = Variable.get("notification_email", default_var="admin@example.com")

    notification_emails = [email.strip() for email in email_string.split(',') if email.strip()]

    # NOTE: The preprocessing task is currently commented out,
    # suggesting it's being handled in another DAG or process
    
    task_preprocess_json = PythonOperator(
        task_id='preprocess_json',
        python_callable=preprocess_json_task,
    )
    

    # OBJECTIVE: Define the NER processing task
    # This task will extract biomedical entities from the preprocessed JSON files
    task_ner_process = PythonOperator(
        # Task identifier used in the Airflow UI
        task_id='ner_process',
        # The function to execute (defined in utils.tasks)
        python_callable=ner_process_task,
        email_on_failure=True,
        email=notification_emails,
    )

    # Set the task as the only one in this DAG
    # No dependencies needed since there's only one active task
    task_preprocess_json >> task_ner_process
