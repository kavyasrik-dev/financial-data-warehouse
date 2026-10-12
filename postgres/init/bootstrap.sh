#!/usr/bin/env bash
set -euo pipefail

required=(
  POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB
  AIRFLOW_DB_USER AIRFLOW_DB_PASSWORD AIRFLOW_DB_NAME
  METABASE_DB_USER METABASE_DB_PASSWORD METABASE_DB_NAME
  WAREHOUSE_DB_USER WAREHOUSE_DB_PASSWORD WAREHOUSE_DB_NAME
  METABASE_REPORTING_DB_USER METABASE_REPORTING_DB_PASSWORD
)

for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Required environment variable ${name} is empty" >&2
    exit 1
  fi
done

export PGPASSWORD="${POSTGRES_PASSWORD}"
psql_args=(--host postgres --username "${POSTGRES_USER}" --set ON_ERROR_STOP=1)

psql "${psql_args[@]}" --dbname "${POSTGRES_DB}" \
  --set airflow_user="${AIRFLOW_DB_USER}" \
  --set airflow_password="${AIRFLOW_DB_PASSWORD}" \
  --set airflow_database="${AIRFLOW_DB_NAME}" \
  --set metabase_user="${METABASE_DB_USER}" \
  --set metabase_password="${METABASE_DB_PASSWORD}" \
  --set metabase_database="${METABASE_DB_NAME}" \
  --set warehouse_user="${WAREHOUSE_DB_USER}" \
  --set warehouse_password="${WAREHOUSE_DB_PASSWORD}" \
  --set warehouse_database="${WAREHOUSE_DB_NAME}" \
  --set reporting_user="${METABASE_REPORTING_DB_USER}" \
  --set reporting_password="${METABASE_REPORTING_DB_PASSWORD}" \
  --file /opt/bootstrap/00-create-app-databases.sql

psql "${psql_args[@]}" --dbname "${WAREHOUSE_DB_NAME}" \
  --set warehouse_user="${WAREHOUSE_DB_USER}" \
  --set reporting_user="${METABASE_REPORTING_DB_USER}" \
  --set warehouse_database="${WAREHOUSE_DB_NAME}" \
  --file /opt/bootstrap/schemas.sql
