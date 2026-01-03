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

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.models.variable import Variable
import sys

# Add paths for imports
sys.path.insert(0, '/opt/airflow/dags/NER')
sys.path.insert(0, '/app/airflow/dags')

# Import all task functions from centralized tasks module
from utils.tasks import (
    initialize_airflow_variables,
    setup_ontologies_task,
    download_vocabulary_task,
    preprocess_json_task,
    ner_process_task,
    validate_results_task
)

# Import configuration
from utils.config import DAGConfig


# -------------------------------------------------------------------------------------------
# DAG CONFIGURATION
# -------------------------------------------------------------------------------------------

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# -------------------------------------------------------------------------------------------
# DAG DEFINITION
# -------------------------------------------------------------------------------------------

# OBJECTIVE: Define the Named Entity Recognition (NER) DAG
# Create a monthly scheduled DAG for NER processing
with DAG(
    # DAG identifier used in the Airflow UI
    dag_id='3_ner_dag',
    # Description of the DAG's purpose
    description='Named Entity Recognition process for biomedical entities extraction',
    # Default arguments for all tasks
    default_args=default_args,
    # Schedule the DAG to run monthly
    schedule_interval='@monthly',
    # Set start date to current time (will run on next schedule after this time)
    start_date=datetime.now(),
    # Don't run for periods that were missed if the scheduler was down
    catchup=False,
    # Add tags for easier filtering in Airflow UI
    tags=['ner', 'biomedical', 'entity-extraction'],
) as dag:
    
    # Get notification emails from Airflow Variables
    email_string = Variable.get("notification_email", default_var="admin@example.com")
    notification_emails = [email.strip() for email in email_string.split(',') if email.strip()]


# -------------------------------------------------------------------------------------------
# TASK DEFINITIONS
# -------------------------------------------------------------------------------------------

    # Task 1: Initialize Airflow variables from configuration
    init_variables = PythonOperator(
        task_id='initialize_variables',
        python_callable=initialize_airflow_variables,
        provide_context=True,
        dag=dag,
    )

    # Task 2: Setup and download ontologies (DOID, ChEBI, HPO, ORDO, etc.)
    setup_ontologies = PythonOperator(
        task_id='setup_ontologies',
        python_callable=setup_ontologies_task,
        provide_context=True,
        dag=dag,
    )

    # Task 3: Download vocabulary files (DrugBank, etc.)
    download_vocabularies = PythonOperator(
        task_id='download_vocabularies',
        python_callable=download_vocabulary_task,
        provide_context=True,
        dag=dag,
    )

    # Task 4: Preprocess biomedical text in JSON files
    preprocess_text = PythonOperator(
        task_id='preprocess_text',
        python_callable=preprocess_json_task,
        provide_context=True,
        dag=dag,
    )

    # Task 5: Extract biomedical entities using NER
    extract_entities = PythonOperator(
        task_id='extract_entities',
        python_callable=ner_process_task,
        provide_context=True,
        dag=dag,
    )

    # Task 6: Validate extraction results
    validate_results = PythonOperator(
        task_id='validate_results',
        python_callable=validate_results_task,
        provide_context=True,
        dag=dag,
    )


# -------------------------------------------------------------------------------------------
# TASK DEPENDENCIES
# -------------------------------------------------------------------------------------------

    # Initialize variables first
    init_variables >> setup_ontologies >> download_vocabularies

    # Preprocessing depends on both ontologies and vocabularies being ready
    [setup_ontologies, download_vocabularies] >> preprocess_text

    # Entity extraction depends on preprocessing
    preprocess_text >> extract_entities

    # Validation is the final step
    extract_entities >> validate_results

# -------------------------------------------------------------------------------------------
# EXAMPLE: Using NER directly in a task
# -------------------------------------------------------------------------------------------

def custom_entity_extraction_task(**kwargs):
    """
    Alternative task showing direct use of StandaloneBioNER
    """
    from NER.standalone_bioner import StandaloneBioNER
    config = DAGConfig()
    
    # Initialize NER
    ner = StandaloneBioNER(
        data_dir=config.ontology_data_dir,
        scripts_dir=config.ontology_scripts_dir
    )
    
    # Extract entities from text
    text = "Patient presents with diabetes mellitus and hypertension"
    
    # Extract disease entities
    disease_entities = ner.extract_entities(text, 'doid')
    
    print(f"\nFound {len(disease_entities)} disease entities:")
    for entity in disease_entities:
        print(f"  - {entity['text']}: {entity.get('uri', 'N/A')}")
    
    # Extract chemical entities
    chemical_entities = ner.extract_entities('glucose insulin aspirin', 'chebi')
    
    print(f"\nFound {len(chemical_entities)} chemical entities:")
    for entity in chemical_entities:
        print(f"  - {entity['text']}: {entity.get('uri', 'N/A')}")