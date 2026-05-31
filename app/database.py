import os

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
