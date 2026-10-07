from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings, secret_value


connect_args = {}
engine_options = {}

if secret_value(settings.DATABASE_URL).startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
    }
else:
    connect_args = {"connect_timeout": 5}
    engine_options = {"pool_pre_ping": True, "pool_timeout": 5}


engine = create_engine(
    secret_value(settings.DATABASE_URL),
    echo=False,
    connect_args=connect_args,
    **engine_options,
)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
