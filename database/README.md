# Database

This directory contains the relations created to send the information to the Neo4j database.

## Table of Contents
1. [Connection](#connection)
2. [Structure](#structure)

## Connection

The connection to the Neo4j database is managed through the `config.ini` file located in the `airflow` directory.

```ini
[neo4j]
uri = neo4j+s://017ef1b2.databases.neo4j.io
user = neo4j
password = WVtqTz2e8SzIHy8U4QqyNbGv4V5R8NgQFytZMe3ATkY
```

**Configuration Parameters:**
- `uri`: The URI of the Neo4j database.
- `user`: The username for the Neo4j database.
- `password`: The password for the Neo4j database.

## Structure

The relations to the Neo4j database are managed through the `knowledge_graph.py` file located in this directory. 

The module is organized as follows:

```bash
database/
├── neo4j.ini
└── knowledge_graph.py
```

- `neo4j.ini`: The configuration file to connect to the Neo4j database.
- `knowledge_graph.py`: The Python script to create the relations to the Neo4j database.