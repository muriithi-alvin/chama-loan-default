"""Database connection helper."""
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

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
