"""Database connection helper."""
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from chama.config import database_url


def get_engine() -> Engine:
    return create_engine(database_url(), future=True)
