from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.tasks import send_to_neo4j_task
from airflow.models.variable import Variable


with DAG(
    # DAG identifier used in the Airflow UI
    '4_neo4j_dag',
    # Description of the DAG's purpose
    description='Send JSON files to Neo4j',
    # Schedule the DAG to run monthly
    schedule_interval='@monthly',
    # Set start date to current time (will run on next schedule after this time)
    start_date=datetime.now(),
    # Don't run for periods that were missed if the scheduler was down
    catchup=False,
) as dag:
    
   
    email_string = Variable.get("notification_email", default_var="admin@example.com")

    notification_emails = [email.strip() for email in email_string.split(',') if email.strip()]
    
    # OBJECTIVE: Define the task to send JSON files to Neo4j
    task_send_to_neo4j = PythonOperator(
        task_id='send_to_neo4j',
        python_callable=send_to_neo4j_task,
        email_on_failure=True, 
        email=notification_emails, 
    )

    task_send_to_neo4j 
