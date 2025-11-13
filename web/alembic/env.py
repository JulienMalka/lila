from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add parent directory to path to allow imports
web_dir = os.path.dirname(os.path.dirname(__file__))
parent_dir = os.path.dirname(web_dir)

# Import models and database configuration
# Try to import as installed package first
try:
    from lila.db import Base, SQLALCHEMY_DATABASE_URL
    import lila.models  # noqa: F401 - Import all models so Alembic can see them
except ImportError:
    # Development mode: add parent to path and import web as package
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # Import web as a package
    import web.db as db
    import web.models  # noqa: F401 - Import all models so Alembic can see them
    Base = db.Base
    SQLALCHEMY_DATABASE_URL = db.SQLALCHEMY_DATABASE_URL

config = context.config

# Override sqlalchemy.url with our database URL from environment/config
if SQLALCHEMY_DATABASE_URL:
    config.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Check if a connection was passed in (for testing)
    connectable = config.attributes.get('connection', None)

    if connectable is None:
        # Normal mode: create engine from config
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    # Determine if we should use context manager or not
    # If connection was provided, it's already managed externally
    connection_provided = config.attributes.get('connection', None) is not None

    def do_run_migrations(connection):
        # Enable batch mode for SQLite to support ALTER TABLE operations
        # SQLite has limited ALTER TABLE support, batch mode works around this
        url = config.get_main_option("sqlalchemy.url") or SQLALCHEMY_DATABASE_URL
        is_sqlite = url and url.startswith('sqlite')

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Enable comparison of types and server defaults for better autogenerate
            compare_type=True,
            compare_server_default=True,
            # Enable batch mode for SQLite to handle ALTER TABLE limitations
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()

    if connection_provided:
        # Connection provided externally (testing), use it directly
        do_run_migrations(connectable)
    else:
        # Create our own connection
        with connectable.connect() as connection:
            do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
