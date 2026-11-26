#!/bin/sh
set -eu

echo "===== KIBABA INITIALISATION ====="

: "${POSTGRES_HOST:=postgres}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

export POSTGRES_HOST POSTGRES_PORT POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB
export PGPASSWORD="$POSTGRES_PASSWORD"

DATA=/app/data
BACKUP="$DATA/persistent"
RELEASE=/release

mkdir -p \
  "$DATA/raw/chama_demo" \
  "$DATA/interim" \
  "$DATA/photos/chama_demo" \
  "$BACKUP"

echo "Waiting for PostgreSQL..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" >/dev/null 2>&1; do
  sleep 2
done

echo "Checking release bundle..."
test -f "$RELEASE/MANIFEST.json"
test -f "$RELEASE/model/MLmodel"
test -f "$RELEASE/data/interim/aliases_chama_demo.csv"

# Seed only missing files. Never overwrite records already on the VM.
for file in "$RELEASE"/data/raw/chama_demo/*.xlsx; do
  test -f "$file" || continue
  destination="$DATA/raw/chama_demo/$(basename "$file")"
  if [ ! -f "$destination" ]; then
    cp "$file" "$destination"
  fi
done

if [ ! -f "$DATA/interim/aliases_chama_demo.csv" ]; then
  cp "$RELEASE/data/interim/aliases_chama_demo.csv" \
     "$DATA/interim/aliases_chama_demo.csv"
fi

echo "Attaching persistent release storage..."
python -m chama.pipeline release-storage attach

echo "Checking whether the database is already initialised..."
TABLE_EXISTS=$(psql \
  -h "$POSTGRES_HOST" \
  -p "$POSTGRES_PORT" \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  -Atqc "SELECT to_regclass('analytics.meetings') IS NOT NULL;")

if [ "$TABLE_EXISTS" = "t" ]; then
  echo "Existing Kibaba database detected. Preserving it."
else
  echo "No existing Kibaba database table detected."

  if find "$BACKUP/db" -maxdepth 1 -type f -name 'kibaba-*.dump' -print -quit | grep -q .; then
    echo "A database backup exists. Attempting restore..."
    python -m chama.pipeline release-storage restore
  else
    echo "No database backup found. This is a fresh installation."
  fi
fi

echo "Running safe first-start procedure..."
python -m chama.pipeline first-start

echo "Saving initial database backup..."
python -m chama.pipeline release-storage save

echo "===== INITIALISATION COMPLETE ====="

