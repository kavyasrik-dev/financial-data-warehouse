ARG AIRFLOW_VERSION=3.3.2
ARG PYTHON_VERSION=3.11

FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

ARG AIRFLOW_VERSION
ARG PYTHON_VERSION

COPY airflow/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt" \
    apache-airflow-providers-fab==3.9.0 \
    apache-airflow-providers-postgres==7.0.2 \
    apache-airflow-providers-standard==1.19.0 && \
    pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -r /tmp/requirements.txt
