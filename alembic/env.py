from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import MetaData
from sqlalchemy import pool

from backend.core.config import settings, secret_value
from backend.database.base import Base

# Import all models so SQLAlchemy registers their tables
from backend.models.organization import Organization
from backend.models.lead import Lead
from backend.models.lead_analysis import LeadAnalysis


# Alembic Config object
config = context.config


# Use the same database URL as the application
config.set_main_option(
    "sqlalchemy.url",
    secret_value(settings.DATABASE_URL).replace("%", "%%"),
)


# Configure Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

from backend.core.logger import configure_logging, event
configure_logging()


# SQLAlchemy metadata used by Alembic autogenerate
import backend.models
target_metadata = Base.metadata



def get_target_metadata() -> MetaData:
    """Return the application's fully registered SQLAlchemy metadata."""
    return Base.metadata


target_metadata = get_target_metadata()


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 5}
        if secret_value(settings.DATABASE_URL).startswith("postgresql+psycopg") else {},
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


import logging
from sqlalchemy.exc import SQLAlchemyError
from alembic.script import ScriptDirectory
target_revision = ",".join(ScriptDirectory.from_config(config).get_heads())
event("migration.started", target_revision=target_revision)
try:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
except Exception as exc:
    event("migration.failed", level=logging.ERROR, exception_type=type(exc).__name__, reason="database_or_schema_failure")
    raise RuntimeError(f"DATABASE_URL migration operation failed ({type(exc).__name__})") from None
else:
    event("migration.completed", target_revision=target_revision)
