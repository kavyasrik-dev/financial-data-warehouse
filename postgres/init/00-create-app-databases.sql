CREATE USER airflow WITH PASSWORD 'airflow';
CREATE DATABASE airflow_metadata OWNER airflow;

CREATE USER metabase WITH PASSWORD 'metabase';
CREATE DATABASE metabase_metadata OWNER metabase;

CREATE USER warehouse_app WITH PASSWORD 'warehouse_app';
GRANT CONNECT ON DATABASE financial_warehouse TO warehouse_app;
