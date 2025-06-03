###############################################################################
#                                                                             #  
# @file: converter_dag.py                                                     #  
# @description: Airflow DAG for file conversion to JSON                       #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This module defines an Airflow DAG (Directed Acyclic Graph) that focuses    #
# specifically on the file conversion process. It transforms various input    #
# file types (XML, CSV, TXT) into a standardized JSON format for further      #
# processing in the data pipeline.                                            #
#                                                                             #  
###############################################################################

from __future__ import annotations

import pendulum
import os # Importe o módulo os
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.tasks import *
from airflow.operators.bash import BashOperator # Importe BashOperator
# from airflow.configuration import conf # Comentado: Não precisamos importar conf para ler env var
from airflow.models.variable import Variable # Importe Variable

# OBJECTIVE: Define the file conversion DAG
# Create a monthly scheduled DAG for converting files to JSON format
with DAG(
    # DAG identifier used in the Airflow UI
    'converter_dag',
    # Description of the DAG's purpose
    description='Convert different types of files to JSON and send to Neo4j',
    # Schedule the DAG to run monthly
    schedule_interval='@monthly',
    # Set start date to current time (will run on next schedule after this time)
    start_date=datetime.now(),
    # Don't run for periods that were missed if the scheduler was down
    catchup=False,
) as dag:
    
    # Obtenha o email da variavel de ambiente
    # Use um valor default caso a variável não esteja definida
    # email_string = os.environ.get("AIRFLOW_NOTIFICATION_EMAIL", "admin@example.com") # Comentado: Não lemos mais da environment variable
    # email_string = conf.get('custom', 'notification_email', fallback='admin@example.com') # Comentado: Não lemos mais do airflow.cfg

    # Obtenha o email da Variável do Airflow
    # Use Variable.get() para ler do banco de dados do Airflow
    email_string = Variable.get("notification_email", default_var="admin@example.com")

    notification_emails = [email.strip() for email in email_string.split(',') if email.strip()]

    # OBJECTIVE: Define the file conversion task
    # This task handles the conversion of various file types to JSON format
    task_convert_files_to_json = PythonOperator(
        # Task identifier used in the Airflow UI
        task_id='convert_files_to_json',
        # The function to execute (defined in utils.tasks)
        python_callable=convert_files_to_json_task,
        email_on_failure=True, # Ativa notificação por falha na task
        email=notification_emails, # Usa a lista de emails da environment variable
    )

    # Tarefa temporária para forçar falha e testar notificação
    task_teste_falha = BashOperator(
        task_id='tarefa_de_teste_que_falha',
        bash_command='exit 1', # Este comando faz a tarefa falhar
        email_on_failure=True, # Ativa notificação por falha na task
        email=notification_emails, # Usa a lista de emails da environment variable
    )

    # Defina a dependência (a tarefa principal vem depois da tarefa de teste)
    # A falha na tarefa de teste impedirá a execução da tarefa principal
    task_teste_falha >> task_convert_files_to_json