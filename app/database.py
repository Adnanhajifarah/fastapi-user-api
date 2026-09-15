import os
from urllib.parse import quote_plus

import psycopg2


def get_connection():
    """Open a PostgreSQL connection."""
    return psycopg2.connect(
        dbname=os.environ.get("DB_NAME", "fast_apidb"),
        user=os.environ.get("DB_USER", "adn"),
        password=os.environ.get("DB_PASSWORD", ""),
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
    )


def database_url() -> str:
    """Build a SQLAlchemy-style URL from the same environment variables used above.

    Alembic is built on SQLAlchemy and needs a URL rather than discrete keyword
    arguments. Deriving it here — instead of hardcoding one in alembic.ini —
    means the app and the migration tool can never drift onto different
    databases, and no credentials end up in version control.
    """
    user = os.environ.get("DB_USER", "adn")
    password = os.environ.get("DB_PASSWORD", "")
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "fast_apidb")

    credentials = quote_plus(user)
    if password:
        credentials += f":{quote_plus(password)}"

    return f"postgresql+psycopg2://{credentials}@{host}:{port}/{name}"
