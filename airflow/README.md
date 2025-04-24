# Airflow

This directory contains the Apache Airflow configuration files and DAGs files.

## Table of Contents
1. [Configuration](#configuration)
2. [Structure](#structure)


## Configuration

The Airflow configuration file is located at /dags/airflow.ini. The configuration file contains the following sections:

```ini
[USER]
username = admin
firstname = Admin
lastname = User
role = Admin
email = admin@example.com
password = admin
```

- `username`: The username of the user.
- `firstname`: The first name of the user.
- `lastname`: The last name of the user.
- `role`: The role of the user.
- `email`: The email address of the user.
- `password`: The password of the user.

## Structure
The module is organized as follows:

```bash
airflow/
├── airflow.db
├── webserver_config.py
├── logs/
└── dags/
    ├── create_user.py    
    ├── jsonify_dag.py
    ├── converter_dag.py
    ├── ner_dag.py
    ├── neo4j_dag.py
    ├── airflow.ini
    └── utils/
        ├── config.py
        └── tasks.py
``` 

- `airflow.db`: SQLite database file storing metadata for the Apache Airflow instance.
- `webserver_config.py`: Configuration file for the Apache Airflow web server.
- `logs`: Directory storing log files of the Apache Airflow instance.
- `create_user.py`: DAG file that creates a user in the Apache Airflow instance.
- `jsonify_dag.py`: DAG file that runs the complete process.
- `converter_dag.py`: DAG file that runs the converter process.
- `ner_dag.py`: DAG file that runs the NER process.
- `neo4j_dag.py`: DAG file that runs the Neo4j process.
- `airflow.ini`: Configuration file for the Apache Airflow instance.
- `config.py`: Configuration file that links the ini file with the code.
- `tasks.py`: File containing tasks for the Apache Airflow instance.
```
