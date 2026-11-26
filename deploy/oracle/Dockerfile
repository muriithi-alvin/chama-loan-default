FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DO_NOT_TRACK=1 \
    MLFLOW_DISABLE_AGENT_HINT=1

# Install build tools, OpenMP, and PostgreSQL 16 client utilities.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl gnupg build-essential g++ libgomp1 libpq-dev \
    && install -d /usr/share/keyrings \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
       | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# Install the exact dependency versions used by the model environment.
RUN pip install -c deploy/huggingface/constraints.txt \
    -e ".[ml,extraction,web]"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

COPY deploy/oracle/init-production.sh /usr/local/bin/kibaba-init
RUN chmod 755 /usr/local/bin/kibaba-init

USER appuser

CMD ["uvicorn", "chama.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
