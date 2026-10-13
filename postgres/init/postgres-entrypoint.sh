#!/usr/bin/env bash
set -Eeuo pipefail

/usr/local/bin/docker-entrypoint.sh "$@" &
postgres_pid=$!

shutdown() {
  kill -TERM "${postgres_pid}" 2>/dev/null || true
  wait "${postgres_pid}" || true
}
trap shutdown TERM INT

until pg_isready --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" >/dev/null 2>&1; do
  if ! kill -0 "${postgres_pid}" 2>/dev/null; then
    wait "${postgres_pid}"
  fi
  sleep 1
done

psql --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" \
  --set ON_ERROR_STOP=1 \
  --set role_name="${POSTGRES_USER}" \
  --set role_password="${POSTGRES_PASSWORD}" <<'SQL'
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'role_name', :'role_password')
\gexec
SQL

wait "${postgres_pid}"
