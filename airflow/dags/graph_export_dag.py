###############################################################################
#                                                                             #
# @file: graph_export_dag.py                                                  #
# @description: DAG to export Neo4j graph relationships to CSV files          #
# @date: June 2025                                                            #
# @version: 1.0                                                               #
#                                                                             #
# Runs after 4_neo4j_dag and exports:                                         #
#   - indicated.csv        (Drug -[TREATS]-> Disease)                         #
#   - contraindicated.csv  (Drug -[CONTRAINDICATED_FOR]-> Disease)            #
#                                                                             #
###############################################################################

from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models.variable import Variable
from utils.tasks import export_graph_task


with DAG(
    '5_graph_export_dag',
    description='Export Neo4j drug-disease relationships to CSV',
    schedule_interval='@monthly',
    start_date=datetime.now(),
    catchup=False,
    tags=['medjsonify', 'Neo4j', 'export', 'csv'],
) as dag:

    email_string = Variable.get("notification_email", default_var="admin@example.com")
    notification_emails = [e.strip() for e in email_string.split(',') if e.strip()]

    task_export_graph = PythonOperator(
        task_id='export_graph_to_csv',
        python_callable=export_graph_task,
        email_on_failure=True,
        email=notification_emails,
    )

    task_export_graph
