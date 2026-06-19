#################################################################################
#                                                                               #  
# @file: medjsonify_dag.py                                                      #  
# @description: Complete MedJsonify pipeline DAG                                #
# @date: May 2025                                                               #
# @version: 2.1                                                                 #  
#                                                                               #  
# This module defines an Airflow DAG (Directed Acyclic Graph) that orchestrates #
# the complete data processing pipeline from JSON conversion to NER processing. #
# It includes tasks for conversion, vocabulary download, preprocessing, and     #
# named entity recognition, with proper dependencies between tasks.             #
#                                                                               #  
# For running individual stages, use the dedicated DAGs:                        #
# - 1_data_acquisition_dag.py (download/extract)                                #
# - 2_converter_dag.py (JSON conversion)                                        #
# - 3_ner_dag.py (NER processing only)                                          #
# - 4_neo4j_dag.py (Neo4j loading only)                                         #
#                                                                               #  
#################################################################################

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models.variable import Variable
from utils.tasks import *

# -------------------------------------------------------------------------------------------
# DAG CONFIGURATION
# -------------------------------------------------------------------------------------------

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

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
    tags=['medjsonify', 'complete-pipeline', 'biomedical', 'ner', 'ontologies'],
) as dag:
    
    email_string = Variable.get("notification_email", default_var="admin@example.com")
    notification_emails = [email.strip() for email in email_string.split(',') if email.strip()]


    # # ═══════════════════════════════════════════════════════════════════════════
    # # STAGE 1: DATA ACQUISITION
    # # ═══════════════════════════════════════════════════════════════════════════
    
    init_variables = PythonOperator(
        task_id='initialize_variables',
        python_callable=initialize_airflow_variables,
        provide_context=True,
    )

    # download_data = PythonOperator(
    #     task_id='download_data',
    #     python_callable=download_zip_task,
    #     email=notification_emails,
    # )

    # unzip_data = PythonOperator(
    #     task_id='unzip_data',
    #     python_callable=unzip_task,
    #     email=notification_emails,
    # )

    # extract_files = PythonOperator(
    #     task_id='extract_files',
    #     python_callable=extract_xml_files_task,
    #     email=notification_emails,
    # )

    
    # ═══════════════════════════════════════════════════════════════════════════
    # STAGE 2: FILE CONVERSION
    # ═══════════════════════════════════════════════════════════════════════════
    
    convert_to_json = PythonOperator(
        task_id='convert_to_json',
        python_callable=convert_files_to_json_task,
        email=notification_emails,
    )

    
    # ═══════════════════════════════════════════════════════════════════════════
    # STAGE 3: NER PREPARATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    setup_ontologies = PythonOperator(
        task_id='setup_ontologies',
        python_callable=setup_ontologies_task,
        provide_context=True,
        email=notification_emails,
    )

    download_vocabularies = PythonOperator(
        task_id='download_vocabularies',
        python_callable=download_vocabulary_task,
        provide_context=True,
        email=notification_emails,
    )

    
    # ═══════════════════════════════════════════════════════════════════════════
    # STAGE 4: NER PROCESSING
    # ═══════════════════════════════════════════════════════════════════════════
    
    preprocess_text = PythonOperator(
        task_id='preprocess_text',
        python_callable=preprocess_json_task,
        provide_context=True,
        email=notification_emails,
    )

    extract_entities = PythonOperator(
        task_id='extract_entities',
        python_callable=ner_process_task,
        provide_context=True,
        email=notification_emails,
    )

    validate_results = PythonOperator(
        task_id='validate_results',
        python_callable=validate_results_task,
        provide_context=True,
        email=notification_emails,
    )

    
    # ═══════════════════════════════════════════════════════════════════════════
    # STAGE 5: DATABASE LOADING
    # ═══════════════════════════════════════════════════════════════════════════
    
    load_to_neo4j = PythonOperator(
        task_id='load_to_neo4j',
        python_callable=send_to_neo4j_task,
        email=notification_emails,
    )


    # ═══════════════════════════════════════════════════════════════════════════
    # STAGE 6: GRAPH EXPORT
    # ═══════════════════════════════════════════════════════════════════════════

    export_graph = PythonOperator(
        task_id='export_graph_to_csv',
        python_callable=export_graph_task,
        email=notification_emails,
    )


    # ═══════════════════════════════════════════════════════════════════════════
    # PIPELINE DEPENDENCIES
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Stage 1: Data Acquisition
    # init_variables >> download_data >> unzip_data >> extract_files
    
    # Stage 2: Conversion (depends on data extraction)
    # extract_files >> 
    convert_to_json
    
    # Stage 3: NER Preparation (parallel setup after initialization)
    init_variables >> setup_ontologies >> download_vocabularies
    
    # Stage 4: NER Processing (depends on both conversion and NER setup)
    [convert_to_json, setup_ontologies, download_vocabularies] >> preprocess_text
    preprocess_text >> extract_entities >> validate_results
    
    # Stage 5: Neo4j Loading (depends on validated NER results)
    validate_results >> load_to_neo4j

    # Stage 6: Graph Export (depends on Neo4j being populated)
    load_to_neo4j >> export_graph


    # ═══════════════════════════════════════════════════════════════════════════
    # STAGE 7: STRUCTURAL SIMILARITY
    # ═══════════════════════════════════════════════════════════════════════════

    compute_similarity = PythonOperator(
        task_id='compute_structural_similarity',
        python_callable=compute_similarity_task,
        email=notification_emails,
    )

    # Stage 7: Similarity (depends on CSVs being exported)
    export_graph >> compute_similarity