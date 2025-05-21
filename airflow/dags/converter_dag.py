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

from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.tasks import *

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
    
    # OBJECTIVE: Define the file conversion task
    # This task handles the conversion of various file types to JSON format
    task_convert_files_to_json = PythonOperator(
        # Task identifier used in the Airflow UI
        task_id='convert_files_to_json',
        # The function to execute (defined in utils.tasks)
        python_callable=convert_files_to_json_task,
    )

    # Set the task as the only one in this DAG
    # No dependencies needed since there's only one task
    task_convert_files_to_json