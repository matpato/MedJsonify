FROM apache/airflow:2.7.2
USER root

RUN apt-get update && \
    apt-get install -y gawk git wget && \
    apt-get clean && \
    mkdir -p /opt/airflow/dags/jsonify/src/types/xml_files && \
    mkdir -p /opt/airflow/dags/database && \
    mkdir -p /opt/airflow/dags/upload && \
    mkdir -p /opt/airflow/dags/NER/data/ontologies && \
    mkdir -p /opt/airflow/dags/NER/data/blacklists && \
    mkdir -p /opt/airflow/dags/NER/merpy/merpy && \
    mkdir -p /opt/airflow/dags/NER/merpy/merpy/MER && \
    chown -R airflow:root /opt/airflow && \
    chmod -R 777 /opt/airflow

# Clone MER repository and set permissions
RUN git clone https://github.com/lasigeBioTM/MER.git /opt/airflow/dags/NER/merpy/merpy/MER && \
    chmod +x /opt/airflow/dags/NER/merpy/merpy/MER/get_entities.sh && \
    chmod +x /opt/airflow/dags/NER/merpy/merpy/MER/produce_data_files.sh && \
    chown -R airflow:root /opt/airflow/dags/NER/merpy/merpy/MER

USER airflow
COPY --chown=airflow:root requirements.txt /opt/airflow/
RUN pip install --no-cache-dir --user -r requirements.txt 

# Copy ontology files and their processed versions
COPY --chown=airflow:root NER/data/ontologies/chebi_lite.owl /opt/airflow/dags/NER/merpy/merpy/MER/data/
COPY --chown=airflow:root NER/data/ontologies/doid.owl /opt/airflow/dags/NER/merpy/merpy/MER/data/
COPY --chown=airflow:root NER/data/ontologies/chebi_lite_*.txt /opt/airflow/dags/NER/merpy/merpy/MER/data/
COPY --chown=airflow:root NER/data/ontologies/chebi_lite_*.tsv /opt/airflow/dags/NER/merpy/merpy/MER/data/
COPY --chown=airflow:root NER/data/ontologies/doid_*.txt /opt/airflow/dags/NER/merpy/merpy/MER/data/
COPY --chown=airflow:root NER/data/ontologies/doid_*.tsv /opt/airflow/dags/NER/merpy/merpy/MER/data/

WORKDIR /opt/airflow/dags/NER/merpy/merpy/MER/

# Verify files exist and run the script
RUN ls -l /opt/airflow/dags/NER/merpy/merpy/MER/data/ && \
    ./produce_data_files.sh /opt/airflow/dags/NER/merpy/merpy/MER/data/chebi_lite.owl && \
    ./produce_data_files.sh /opt/airflow/dags/NER/merpy/merpy/MER/data/doid.owl

WORKDIR /opt/airflow/