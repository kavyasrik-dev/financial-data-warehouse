#!/usr/bin/env bash
set -Eeuo pipefail

ready_file=/tmp/postgres-password-ready
data_directory="${PGDATA:-/var/lib/postgresql/data}"
rm -f "${ready_file}"

if [[ ! -s "${data_directory}/PG_VERSION" ]]; then
  touch "${ready_file}"
  exec /usr/local/bin/docker-entrypoint.sh "$@"
fi

/usr/local/bin/docker-entrypoint.sh "$@" -c "listen_addresses=" &
postgres_pid=$!

shutdown() {
  kill -TERM "${postgres_pid}" 2>/dev/null || true
  wait "${postgres_pid}" || true
}
trap shutdown TERM INT

until pg_isready --host /var/run/postgresql --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" >/dev/null 2>&1; do
  if ! kill -0 "${postgres_pid}" 2>/dev/null; then
    wait "${postgres_pid}"
  fi
  sleep 1
done

psql --host /var/run/postgresql --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" \
  --set ON_ERROR_STOP=1 \
  --set role_name="${POSTGRES_USER}" \
  --set role_password="${POSTGRES_PASSWORD}" <<'SQL'
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'role_name', :'role_password')
\gexec
SQL

kill -TERM "${postgres_pid}"
wait "${postgres_pid}"
trap - TERM INT

touch "${ready_file}"
exec /usr/local/bin/docker-entrypoint.sh "$@"
