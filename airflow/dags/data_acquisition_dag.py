###############################################################################
#                                                                             #  
# @file: data_acquisition_dag.py                                              #  
# @description: Standalone DAG for data download and extraction               #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This DAG handles only the data acquisition phase:                           #
# - Download ZIP files from configured URLs                                   #
# - Extract ZIP archives                                                      #
# - Extract specific files (XML, CSV, TXT) to processing directories          #
#                                                                             #  
# Use this when you only need to refresh source data without reprocessing.    #
#                                                                             #  
###############################################################################

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models.variable import Variable
from utils.tasks import (
    initialize_airflow_variables,
    download_zip_task,
    unzip_task,
    extract_xml_files_task
)

# -------------------------------------------------------------------------------------------
# DAG CONFIGURATION
# -------------------------------------------------------------------------------------------

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,  # More retries for network operations
    'retry_delay': timedelta(minutes=5),
}

# -------------------------------------------------------------------------------------------
# DAG DEFINITION
# -------------------------------------------------------------------------------------------

with DAG(
    dag_id='1_data_acquisition_dag',
    description='Download and extract medical data from external sources',
    default_args=default_args,
    schedule_interval='@monthly',  # Run monthly to check for new data
    start_date=datetime.now(),
    catchup=False,
    tags=['data-acquisition', 'download', 'extraction'],
) as dag:
    
    # Get notification emails
    email_string = Variable.get("notification_email", default_var="admin@example.com")
    notification_emails = [email.strip() for email in email_string.split(',') if email.strip()]

    
    # -------------------------------------------------------------------------------------------
    # TASK DEFINITIONS
    # -------------------------------------------------------------------------------------------
    
    # Initialize Airflow variables
    init_variables = PythonOperator(
        task_id='initialize_variables',
        python_callable=initialize_airflow_variables,
        provide_context=True,
    )

    # Download ZIP files from configured URLs
    download_data = PythonOperator(
        task_id='download_data',
        python_callable=download_zip_task,
        email=notification_emails,
    )

    # Extract all ZIP archives
    unzip_data = PythonOperator(
        task_id='unzip_data',
        python_callable=unzip_task,
        email=notification_emails,
    )

    # Extract specific files (XML, CSV, TXT) to processing directories
    extract_files = PythonOperator(
        task_id='extract_files',
        python_callable=extract_xml_files_task,
        email=notification_emails,
    )

    
    # -------------------------------------------------------------------------------------------
    # TASK DEPENDENCIES
    # -------------------------------------------------------------------------------------------
    
    init_variables >> download_data >> unzip_data >> extract_files