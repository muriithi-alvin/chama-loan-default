"""Database connection helper."""
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from chama.config import database_url


def get_engine() -> Engine:
    return create_engine(database_url(), future=True)


def table_exists(conn: Connection, name: str) -> bool:
    """True if a table such as 'raw.statements' exists."""
    return conn.execute(text("SELECT to_regclass(:t)"), {"t": name}).scalar() is not None
