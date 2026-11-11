#!/usr/bin/env bash
# Starts Kibaba's release (D-032, D-033, D-041). The database runs inside the
# container. With the storage bucket mounted at BACKUP_DIR, the records saved
# there last time are restored, and the pages, photos and names added are
# written into the bucket, so they survive restarts. Without it, the starting
# records are loaded and scored each time. Then the API, the worker and the
# pages run side by side. If any of the three stops, the container stops and
# Hugging Face starts it again; on the way down the database is saved once more.
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

if [ -n "${BACKUP_DIR:-}" ] && python -m chama.pipeline release-storage check; then
  export PHOTO_DIR="$BACKUP_DIR/uploads"
  python -m chama.pipeline release-storage attach
  python -m chama.pipeline release-storage restore
else
  echo "WARNING: no storage bucket at ${BACKUP_DIR:-(BACKUP_DIR not set)}: pages added here are lost at the next restart"
  export BACKUP_DIR=""
fi

python -m chama.pipeline first-start      # loads and scores only when the database is empty
if [ -n "$BACKUP_DIR" ]; then
  python -m chama.pipeline release-storage save || echo "WARNING: the first save to the bucket failed"
fi

stop() {
  if [ -n "$BACKUP_DIR" ]; then
    timeout 25 python -m chama.pipeline release-storage save || echo "WARNING: the last save failed"
  fi
  kill $(jobs -p) 2>/dev/null || true
  exit 0
}
trap stop TERM INT

python -m uvicorn chama.web.app:app --host 127.0.0.1 --port 8000 &
python -m chama.web.worker &
(cd frontend/.next/standalone && PORT=7860 HOSTNAME=0.0.0.0 exec node server.js) &

set +e
wait -n                                  # one part stopped: save, stop the others, and let Hugging Face restart it
code=$?
if [ -n "$BACKUP_DIR" ]; then
  timeout 25 python -m chama.pipeline release-storage save || echo "WARNING: the last save failed"
fi
kill $(jobs -p) 2>/dev/null || true
exit $code
