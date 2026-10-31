# Standalone mode

Runs the MedJsonify pipeline without Airflow, one step at a time, in a light Docker image.
The task code, folders and `.ini` files are the same as in Airflow mode. Run every command from the main folder.

## Steps

```
download → convert → stats → ontologies → vocabulary → preprocess → ner → validate → graph → export
```

## Commands

```bash
bash standalone/run_medjsonify.sh --list               # build the image, list the tasks
bash standalone/run_medjsonify.sh                      # whole pipeline
bash standalone/run_medjsonify.sh --step convert       # one step (name or number)
bash standalone/run_medjsonify.sh --from preprocess    # from a step to the end
bash standalone/run_medjsonify.sh --ds 2025-05-01      # run date (used in file names)
bash standalone/run_medjsonify.sh --shell '<command>'  # any command in the container
bash standalone/run_medjsonify.sh --rebuild --check    # rebuild the image, check imports
```

Rebuild (`--rebuild`) after changing `requirements.txt`, `standalone/requirements-extra.txt`, `standalone/Dockerfile` or `standalone/jsonifyer_python_converter.py`. Code and `.ini` changes need no rebuild.

## Files

| File | Purpose |
|---|---|
| `run_medjsonify.sh` | Runner: builds the image, runs each step in its own container, writes logs to `standalone/logs/` |
| `run_task.py` | Calls a DAG task function without Airflow |
| `Dockerfile` | Python 3.8 image with `requirements.txt` (without Airflow) and the patched jsonifyer |
| `jsonifyer_python_converter.py` | Patched jsonifyer converter (attribute pairs, full element text) |
| `fetch_ontologies.py` | Downloads and processes the ontologies listed in `NER/bioner.ini` |
| `check_imports.py` | Lists packages the code imports but the image lacks |
| `dataflow_queries.md` | Commands and Cypher queries for every table and figure of the paper |

## Neo4j

The graph step uses the `medjsonify_neo4j` container if it exists, otherwise it starts a Neo4j 5 container with the same settings. Browser: <http://localhost:7474> (user `neo4j`, password `testpassword`). After changing the loading code, empty the graph (`MATCH (n) DETACH DELETE n;`) before loading it again.

## Settings

Environment variables in front of the command, e.g. `TASK_GRAPH=send_to_neo4j_task bash standalone/run_medjsonify.sh --step graph`:
`TASK_DOWNLOAD`, `TASK_GRAPH` (default `send_to_neo4j_task`), `TASK_EXPORT` (default `export_graph_task`), `ONTOLOGY_SOURCE` (`fetch` or `task`), `IMAGE`, `DOCKER`, `NEO4J_AUTH`.