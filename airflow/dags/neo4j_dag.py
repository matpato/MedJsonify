###############################################################################
#                                                                             #  
# @author: Carolina Pereira                                                   #  
# @email: carolinadpereira18@gmail.com                                        #
# @version: 1.0                                                               #  
# ISEL - Instituto Superior de Engenharia de Lisboa                           #
#                                                                             #            
###############################################################################

from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.tasks import send_to_neo4j_task


with DAG(
    'neo4j_dag',
    description='Send JSON files to Neo4j',
    schedule_interval='@monthly',
    start_date=datetime.now(),
    catchup=False,
) as dag:
    
    task_send_to_neo4j = PythonOperator(
        task_id='send_to_neo4j',
        python_callable=send_to_neo4j_task,
    )

    task_send_to_neo4j 
