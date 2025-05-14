FROM apache/airflow:2.7.2
USER root

RUN apt-get update && \
    apt-get install -y gawk git && \
    apt-get clean && \
    mkdir -p /opt/airflow/dags/jsonify/src/types/xml_files && \
    mkdir -p /opt/airflow/dags/database && \
    mkdir -p /opt/airflow/dags/upload && \
    mkdir -p /opt/airflow/dags/NER/data/ontologies && \
    mkdir -p /opt/airflow/dags/NER/data/blacklists && \
    mkdir -p /opt/airflow/dags/NER/merpy/merpy && \
    chown -R airflow:root /opt/airflow && \
    chmod -R 777 /opt/airflow

RUN git clone https://github.com/lasigeBioTM/MER.git /opt/airflow/dags/NER/merpy/merpy/MER && \
    chmod +x /opt/airflow/dags/NER/merpy/merpy/MER/get_entities.sh

ADD http://purl.obolibrary.org/obo/chebi/chebi_lite.owl /opt/airflow/dags/NER/data/ontologies/
ADD http://purl.obolibrary.org/obo/doid.owl /opt/airflow/dags/NER/data/ontologies/

USER airflow
COPY --chown=airflow:root requirements.txt /opt/airflow/
RUN pip install --no-cache-dir --user -r requirements.txt 

WORKDIR /opt/airflow