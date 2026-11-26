"""Shared test fixtures.

`fresh_db`: the separate test database `chama_test` on the same PostgreSQL
server as .env (created if missing), never the real `chama` database, with
every sql/*.sql file run on empty schemas. Once per test module; skipped when
PostgreSQL is not running. (test_web_db.py keeps a fixture of its own.)
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from chama.db import SQL_DIR

TEST_DB = "chama_test"


def _url(database: str) -> str:
    user, password = os.getenv("POSTGRES_USER", "chama"), os.getenv("POSTGRES_PASSWORD", "")
    host, port = os.getenv("POSTGRES_HOST", "localhost"), os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


@pytest.fixture(scope="module")
def fresh_db():
    try:
        admin = create_engine(_url(os.getenv("POSTGRES_DB", "chama")), isolation_level="AUTOCOMMIT",
                              connect_args={"connect_timeout": 3})
        with admin.connect() as conn:
            if not conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": TEST_DB}).first():
                conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    except OperationalError:
        pytest.skip("PostgreSQL is not running (docker compose up -d)")
    eng = create_engine(_url(TEST_DB))
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS app, private, analytics CASCADE"))
        for path in sorted(SQL_DIR.glob("*.sql")):
            conn.exec_driver_sql(path.read_text(encoding="utf-8"))
        conn.execute(text("CREATE TABLE analytics.meetings (chama_id text, page_no int, meeting_month date, "
                          "meeting_date date, date_source text, source_photo text, source_file text)"))
    yield eng
    eng.dispose()
