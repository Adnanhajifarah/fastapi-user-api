"""Alembic environment configuration.

Two deliberate choices here, both worth being able to defend:

1. The database URL is pulled from ``app.database.database_url()`` rather than
   from ``alembic.ini``. The app and the migrations therefore read the same
   ``DB_*`` environment variables and cannot drift onto different databases,
   and no credentials are committed to the repository.

2. ``target_metadata`` stays ``None``. Autogenerate works by diffing SQLAlchemy
   model definitions against the live database, and this project talks to
   Postgres through raw psycopg2 with hand-written SQL — there are no models to
   diff. Migrations here are written by hand, which also keeps the schema
   honest: every column exists because it was deliberately added, not because a
   model changed and a tool inferred a diff.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.database import database_url

config = context.config

# Inject the URL built from DB_* environment variables. set_main_option escapes
# '%' for us, which matters because passwords are URL-encoded and can contain
# percent signs that configparser would otherwise treat as interpolation.
config.set_main_option("sqlalchemy.url", database_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No SQLAlchemy models in this project, so nothing to autogenerate against.
target_metadata = None


def run_migrations_offline() -> None:
    """Emit migrations as SQL text instead of running them.

    Useful when a DBA has to review or apply the SQL by hand, which is common
    in environments where the application cannot hold DDL privileges.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and apply migrations directly."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
