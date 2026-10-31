# MedJsonify standalone image -- light, without Airflow
#
# Plain Python plus the packages in requirements.txt, minus Airflow itself
# (apache-airflow and its providers are skipped). The DAG file is imported
# with a stand-in for Airflow (see run_task.py), so it is not needed.
#
# Python 3.8 matches the Airflow 2.7.2 image used by docker-compose, so both
# modes run the code on the same Python version.
#
# Build context = the MedJsonify main folder (run_medjsonify.sh does this),
# so requirements.txt below is MedJsonify/requirements.txt. By hand:
#   docker build -f standalone/Dockerfile -t medjsonify-standalone:latest .

ARG PYTHON_VERSION=3.8
FROM python:${PYTHON_VERSION}-slim

# Tools used by the ontology shell scripts, as in the main Dockerfile, plus
# what is needed to compile a Python package when no ready-made one exists
# (e.g. lxml needs libxml2/libxslt; the Airflow image already has these)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        gawk git wget curl unzip ca-certificates \
        build-essential pkg-config libxml2-dev libxslt1-dev zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

# Python packages, without Airflow.
#  --prefer-binary   take the newest version that comes ready-made (a wheel)
#                    instead of compiling a newer one from source
#  --retries/timeout so a slow download does not abort the build
COPY requirements.txt /tmp/requirements.txt
RUN grep -viE '^[[:space:]]*apache-airflow' /tmp/requirements.txt > /tmp/requirements-standalone.txt \
 && echo "Skipped for standalone mode:" \
 && (grep -iE '^[[:space:]]*apache-airflow' /tmp/requirements.txt || echo "  (nothing)") \
 && pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --prefer-binary --default-timeout=120 --retries 10 \
        -r /tmp/requirements-standalone.txt

# Packages that Airflow would otherwise bring in (requests, tenacity, ...).
# A separate step, so editing this file does not reinstall everything above.
COPY standalone/requirements-extra.txt /tmp/requirements-extra.txt
RUN pip install --no-cache-dir --prefer-binary --default-timeout=120 --retries 10 \
        -r /tmp/requirements-extra.txt

# jsonifyer, installed inside the image (replaces the PyPI version from
# requirements.txt): the GitHub source at a fixed commit, with
# converter/python_converter.py replaced by the fixed copy in
# standalone/jsonifyer_python_converter.py (the ingredient `pairs` option:
# '@classCode' crashed and 'a/b' paths came back empty). The build checks
# that the fix is in place.
ARG JSONIFYER_REPO=https://github.com/crpereir/jsonifyer.git
ARG JSONIFYER_COMMIT=59f94af5ac56841318ad1fc3dc114f74516d7b68
COPY standalone/jsonifyer_python_converter.py /tmp/jsonifyer_python_converter.py
RUN git clone --quiet "$JSONIFYER_REPO" /tmp/jsonifyer \
 && cd /tmp/jsonifyer \
 && git checkout --quiet "$JSONIFYER_COMMIT" \
 && cp /tmp/jsonifyer_python_converter.py src/jsonifyer/converter/python_converter.py \
 && pip install --no-cache-dir --force-reinstall --no-deps /tmp/jsonifyer \
 && cd / && rm -rf /tmp/jsonifyer \
 && python -c "from jsonifyer.converter.python_converter import _pair_value; print('jsonifyer with pairs fix installed')"

# Same folder layout and import path as the Airflow containers
RUN mkdir -p /opt/airflow/dags /opt/airflow/logs && chmod -R 777 /opt/airflow
ENV PYTHONPATH=/opt/airflow/dags/jsonifyer_src:/opt/airflow/dags:/opt/airflow/dags/jsonify/src \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp
WORKDIR /opt/airflow