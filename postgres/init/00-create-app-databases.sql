SELECT format('CREATE ROLE %I LOGIN', :'airflow_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'airflow_user')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'airflow_user', :'airflow_password')
\gexec

SELECT format('CREATE ROLE %I LOGIN', :'metabase_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'metabase_user')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'metabase_user', :'metabase_password')
\gexec

SELECT format('CREATE ROLE %I LOGIN', :'warehouse_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'warehouse_user')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'warehouse_user', :'warehouse_password')
\gexec

SELECT format('CREATE ROLE %I LOGIN', :'reporting_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'reporting_user')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'reporting_user', :'reporting_password')
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'airflow_database', :'airflow_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'airflow_database')
\gexec

SELECT format('ALTER DATABASE %I OWNER TO %I', :'airflow_database', :'airflow_user')
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'metabase_database', :'metabase_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'metabase_database')
\gexec

SELECT format('ALTER DATABASE %I OWNER TO %I', :'metabase_database', :'metabase_user')
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'warehouse_database', :'warehouse_user')
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'warehouse_database', :'reporting_user')
\gexec
