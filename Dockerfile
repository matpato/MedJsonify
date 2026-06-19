FROM apache/airflow:2.7.2

# Switch to root for system packages
USER root

# Install required system packages
RUN apt-get update && \
    apt-get install -y \
        gawk \
        git \
        wget \
        sed \
        grep \
        bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create directory structure for Airflow DAGs
# These will be overridden by volume mounts, but good to have for structure
RUN mkdir -p /opt/airflow/dags/NER/ontologies/data && \
    mkdir -p /opt/airflow/dags/NER/ontologies/scripts && \
    mkdir -p /opt/airflow/dags/NER/data/blacklists && \
    mkdir -p /opt/airflow/dags/NER/data/entities && \
    mkdir -p /opt/airflow/dags/NER/data/preprocessing && \
    mkdir -p /opt/airflow/dags/jsonify/output && \
    mkdir -p /opt/airflow/dags/jsonify/src/types/xml_files && \
    mkdir -p /opt/airflow/dags/jsonify/src/types/csv_files && \
    mkdir -p /opt/airflow/dags/jsonify/src/types/txt_files && \
    mkdir -p /opt/airflow/dags/database && \
    mkdir -p /opt/airflow/dags/upload && \
    mkdir -p /opt/airflow/dags/utils

# Set correct permissions for Airflow directories
RUN chown -R airflow:root /opt/airflow && \
    chmod -R 775 /opt/airflow/dags

# Switch back to airflow user
USER airflow

# Copy requirements and install Python packages
COPY --chown=airflow:root requirements.txt /opt/airflow/requirements.txt
RUN pip install --no-cache-dir --user -r /opt/airflow/requirements.txt

# Happens when you run: docker-compose build
COPY ./03_NER /opt/airflow/dags/NER          
RUN find /opt/airflow/dags/NER -type f -name "*.sh" -exec chmod +x {} \; || true

# Set Python path to include DAGs directory
# This ensures all modules under /opt/airflow/dags can be imported
ENV PYTHONPATH="${PYTHONPATH}:/opt/airflow/dags:/opt/airflow/dags/jsonify/src"

# Set working directory
WORKDIR /opt/airflow

# Note: Actual code files will be mounted via docker-compose volumes
# This keeps the image lightweight and allows for easy code updates
