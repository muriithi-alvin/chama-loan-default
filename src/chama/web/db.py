"""One database engine for the web server and the worker."""
from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

from chama.config import database_url


@lru_cache
def engine() -> Engine:
    return create_engine(database_url(), future=True, pool_pre_ping=True, pool_size=5,
                         max_overflow=5)


def connection() -> Iterator[Connection]:
    """FastAPI dependency: a connection inside a transaction, committed at the end."""
    with engine().begin() as conn:
        yield conn


# A route parameter typed `Conn` gets the request's connection.
Conn = Annotated[Connection, Depends(connection)]
