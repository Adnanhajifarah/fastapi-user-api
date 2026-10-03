import os
from contextlib import contextmanager
from urllib.parse import quote_plus

from psycopg2 import pool as psycopg2_pool

# Created on first use rather than at import time, so simply importing this
# module never tries to reach the database. Tests and tooling can import the app
# without a running Postgres.
_connection_pool = None


def _connection_settings() -> dict:
    """Read database settings from the environment.

    One function so the pool and database_url() can never disagree about which
    database they mean.
    """
    return {
        "dbname": os.environ.get("DB_NAME", "fast_apidb"),
        "user": os.environ.get("DB_USER", "adn"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": os.environ.get("DB_PORT", "5432"),
    }


def _get_pool() -> psycopg2_pool.ThreadedConnectionPool:
    """Return the shared connection pool, creating it on first call.

    Opening a connection to Postgres means a TCP handshake plus authentication,
    and the server only permits a limited number at once (100 by default).
    Opening a fresh one per request is like hanging up and redialling for every
    sentence of a phone call. A pool opens a few, keeps them, and lends them out.

    ThreadedConnectionPool rather than SimpleConnectionPool because FastAPI runs
    non-async endpoints in a thread pool, so several threads can ask for a
    connection at the same moment.
    """
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = psycopg2_pool.ThreadedConnectionPool(
            minconn=int(os.environ.get("DB_POOL_MIN", "1")),
            maxconn=int(os.environ.get("DB_POOL_MAX", "10")),
            **_connection_settings(),
        )
    return _connection_pool


@contextmanager
def get_cursor(commit: bool = False):
    """Borrow a connection from the pool and yield a cursor on it.

    The `finally` block is the whole point: the connection goes back to the pool
    whether the query succeeded, raised, or the calling code blew up. The old
    code closed connections only on the success path, so any failed query leaked
    one permanently.

    Pass commit=True for statements that change data.
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()
        else:
            # Even a plain SELECT opens a transaction in Postgres. Roll it back
            # so the connection returns to the pool clean, instead of sitting
            # "idle in transaction" and holding locks.
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def close_pool() -> None:
    """Close every pooled connection. Called on application shutdown."""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None


def database_url() -> str:
    """Build a SQLAlchemy-style URL from the same settings the pool uses.

    Alembic is built on SQLAlchemy and needs a URL rather than discrete keyword
    arguments. Deriving it here - instead of hardcoding one in alembic.ini -
    means the app and the migration tool can never drift onto different
    databases, and no credentials end up in version control.
    """
    settings = _connection_settings()

    credentials = quote_plus(settings["user"])
    if settings["password"]:
        credentials += f":{quote_plus(settings['password'])}"

    return (
        f"postgresql+psycopg2://{credentials}"
        f"@{settings['host']}:{settings['port']}/{settings['dbname']}"
    )
