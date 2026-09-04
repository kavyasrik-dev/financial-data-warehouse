DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'airflow') THEN
        CREATE ROLE airflow WITH LOGIN PASSWORD 'airflow';
    ELSE
        ALTER ROLE airflow WITH LOGIN PASSWORD 'airflow';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metabase') THEN
        CREATE ROLE metabase WITH LOGIN PASSWORD 'metabase';
    ELSE
        ALTER ROLE metabase WITH LOGIN PASSWORD 'metabase';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'warehouse_app') THEN
        CREATE ROLE warehouse_app WITH LOGIN PASSWORD 'warehouse_app';
    ELSE
        ALTER ROLE warehouse_app WITH LOGIN PASSWORD 'warehouse_app';
    END IF;
END
$$;

SELECT 'CREATE DATABASE airflow_metadata OWNER airflow'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'airflow_metadata')\gexec

SELECT 'ALTER DATABASE airflow_metadata OWNER TO airflow'
WHERE EXISTS (SELECT 1 FROM pg_database WHERE datname = 'airflow_metadata')\gexec

SELECT 'CREATE DATABASE metabase_metadata OWNER metabase'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'metabase_metadata')\gexec

SELECT 'ALTER DATABASE metabase_metadata OWNER TO metabase'
WHERE EXISTS (SELECT 1 FROM pg_database WHERE datname = 'metabase_metadata')\gexec

GRANT CONNECT ON DATABASE financial_warehouse TO warehouse_app;
