"""Database connection helper."""
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from chama import StepFailed
from chama.config import PROJECT_ROOT, database_url

SQL_DIR = PROJECT_ROOT / "sql"


def get_engine() -> Engine:
    return create_engine(database_url(), future=True)


def create_schemas(engine: Engine) -> None:
    """Run sql/*.sql: the schemas and private tables. Safe to re-run.

    Docker runs these files only when the database is first created; running
    them here also sets up a database made some other way.
    """
    with engine.begin() as conn:
        for path in sorted(SQL_DIR.glob("*.sql")):
            conn.exec_driver_sql(path.read_text(encoding="utf-8"))


def table_exists(conn: Connection, name: str) -> bool:
    """True if a table such as 'raw.statements' exists."""
    return conn.execute(text("SELECT to_regclass(:t)"), {"t": name}).scalar() is not None


def add_missing_columns(conn: Connection, schema: str, table: str, columns) -> list[str]:
    """Add the columns an existing table lacks, as text, e.g. after the raw
    format gains a column. Returns the names added."""
    existing = {
        row[0]
        for row in conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t"
            ),
            {"s": schema, "t": table},
        )
    }
    added = [c for c in columns if c not in existing]
    for column in added:
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", column):
            raise StepFailed(f"Cannot add column {column!r} to {schema}.{table}: rename it in the file")
        conn.execute(text(f'ALTER TABLE {schema}.{table} ADD COLUMN "{column}" TEXT'))
    return added
