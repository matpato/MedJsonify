###############################################################################
#                                                                             #
# @file: similarity_dag.py                                                    #
# @description: DAG to compute structural similarity between CHEBI drugs      #
# @date: June 2025                                                            #
# @version: 1.0                                                               #
#                                                                             #
# Runs after 5_graph_export_dag and produces:                                 #
#   - similar.csv  (drugsA, drugsB, tanimoto, morgan) with tanimoto < 0.7    #
#                                                                             #
###############################################################################

from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models.variable import Variable
from utils.tasks import compute_similarity_task


with DAG(
    '6_similarity_dag',
    description='Compute structural similarity between CHEBI drugs and write similar.csv',
    schedule_interval='@monthly',
    start_date=datetime.now(),
    catchup=False,
    tags=['medjsonify', 'similarity', 'rdkit', 'chebi'],
) as dag:

    email_string = Variable.get("notification_email", default_var="admin@example.com")
    notification_emails = [e.strip() for e in email_string.split(',') if e.strip()]

    task_compute_similarity = PythonOperator(
        task_id='compute_structural_similarity',
        python_callable=compute_similarity_task,
        email_on_failure=True,
        email=notification_emails,
    )

    task_compute_similarity
