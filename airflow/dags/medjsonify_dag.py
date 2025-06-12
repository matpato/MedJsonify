#################################################################################
#                                                                               #  
# @file: jsonify_dag.py                                                         #  
# @description: Airflow DAG for the complete data processing pipeline           #
# @date: May 2025                                                               #
# @version: 2.0                                                                 #  
#                                                                               #  
# This module defines an Airflow DAG (Directed Acyclic Graph) that orchestrates #
# the complete data processing pipeline from JSON conversion to NER processing. #
# It includes tasks for conversion, vocabulary download, preprocessing, and     #
# named entity recognition, with proper dependencies between tasks.             #
#                                                                               #  
#################################################################################

from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.tasks import *
from airflow.models.variable import Variable

# OBJECTIVE: Define the complete data processing pipeline DAG
# Create a monthly scheduled DAG for the end-to-end process
with DAG(
    # DAG identifier used in the Airflow UI
    'medjsonify_dag',
    # Description of the DAG's purpose
    description='Full pipeline for the MedJsonify project (accessing data, converting to JSON, applying NER and sending to Neo4j)',
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

    # NOTE: Initial data acquisition tasks are currently commented out,
    # suggesting they might be handled manually or in another process
    
    # OBJECTIVE: Download data from external sources
    task_download_from_url = PythonOperator(
        task_id='download_from_url',
        python_callable=download_zip_task,
    )

    # OBJECTIVE: Extract downloaded ZIP files
    task_unzip_directories = PythonOperator(
        task_id='unzip_directories',
        python_callable=unzip_task,
    )

    # OBJECTIVE: Extract specific files from the unzipped directories
    task_extract_files = PythonOperator(
        task_id='extract_files',
        python_callable=extract_xml_files_task,
    )

    # OBJECTIVE: Convert extracted files to JSON format
    # This task transforms XML/CSV/TXT files to a standardized JSON format
    task_convert_files_to_json = PythonOperator(
        # Task identifier used in the Airflow UI
        task_id='convert_files_to_json',
        # The function to execute (defined in utils.tasks)
        python_callable=convert_files_to_json_task,
        email_on_failure=True,
        email=notification_emails,
    )
    
    # OBJECTIVE: Download vocabulary files needed for NER processing
    # This task downloads and prepares the vocabularies and ontologies used for entity recognition
    task_download_vocabulary = PythonOperator(
        task_id='download_vocabulary',
        python_callable=download_vocabulary_task,
        email_on_failure=True,
        email=notification_emails,
    )

    # OBJECTIVE: Preprocess JSON data for NER
    # This task prepares the JSON data by cleaning, normalizing, and structuring text
    task_preprocess_json = PythonOperator(
        task_id='preprocess_json',
        python_callable=preprocess_json_task,
        email_on_failure=True,
        email=notification_emails,
    )
    
    # OBJECTIVE: Run Named Entity Recognition process
    # This task identifies and extracts biomedical entities from the preprocessed text
    task_ner_process = PythonOperator(
        task_id='ner_process',
        python_callable=ner_process_task,
        email_on_failure=True,
        email=notification_emails,
    )

    # OBJECTIVE: Send processed data to Neo4j database
    task_send_to_neo4j = PythonOperator(
        task_id='send_to_neo4j',
        python_callable=send_to_neo4j_task,
        email_on_failure=True,
        email=notification_emails,
    )

    # OBJECTIVE: Define the DAG task dependencies/workflow
    # The commented-out section represents the full pipeline including data acquisition
    # task_download_from_url >> task_unzip_directories >> task_extract_files >> 
    
    # Define the workflow: conversion → vocabulary → preprocessing → NER
    # Each task waits for the previous one to complete successfully
    task_download_from_url >> task_unzip_directories >> task_extract_files >> task_convert_files_to_json >> task_download_vocabulary >> task_preprocess_json >> task_ner_process >> task_send_to_neo4j