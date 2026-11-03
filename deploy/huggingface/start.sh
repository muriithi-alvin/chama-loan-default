#!/usr/bin/env bash
# Starts Kibaba's release (D-032, D-033). The database runs inside the container
# and starts empty each time: the demo chama is loaded and scored and its two
# accounts added. Then the API, the worker and the pages run side by side. If
# any of the three stops, the container stops and Hugging Face starts it again.
set -euo pipefail
cd /app

export PATH="$(ls -d /usr/lib/postgresql/*/bin | sort -V | tail -1):$PATH"
export PGDATA=/tmp/pgdata POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5432 POSTGRES_USER=kibaba POSTGRES_DB=kibaba
POSTGRES_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"
export POSTGRES_PASSWORD

rm -rf "$PGDATA"
printf '%s' "$POSTGRES_PASSWORD" > /tmp/pgpass
initdb -D "$PGDATA" -U "$POSTGRES_USER" --pwfile=/tmp/pgpass --auth=scram-sha-256 -E UTF8 --locale=C.UTF-8 > /dev/null
rm -f /tmp/pgpass
pg_ctl -D "$PGDATA" -w -l /tmp/postgres.log \
  -o "-c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp -c max_parallel_workers_per_gather=0" start
PGPASSWORD="$POSTGRES_PASSWORD" createdb -h 127.0.0.1 -U "$POSTGRES_USER" "$POSTGRES_DB"

python -m chama.pipeline first-start

python -m uvicorn chama.web.app:app --host 127.0.0.1 --port 8000 &
python -m chama.web.worker &
(cd frontend/.next/standalone && PORT=7860 HOSTNAME=0.0.0.0 exec node server.js) &

wait -n
exit $?
