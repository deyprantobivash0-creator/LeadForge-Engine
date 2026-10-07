"""Processing-claim migration uses disposable SQLite databases only."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.core.config import settings


PREVIOUS = "d4c3b2a1e0f9"
HEAD = "e5d4c3b2a1f0"
ROOT = Path(__file__).resolve().parents[1]


def test_processing_claim_upgrade_preserves_populated_data_and_downgrades(tmp_path, monkeypatch):
    path = tmp_path / "processing.db"
    assert path.parent.name.startswith("test_")
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{path.as_posix()}")
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, PREVIOUS)
    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO organizations (id,name,slug,plan,monthly_lead_limit,is_active,created_at) VALUES (1,'Org','org','standard',500,1,CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO leads (id,organization_id,company,email,source,status,processing_status,created_at) VALUES (1,1,'Company','lead@example.com','test','New','processing',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO lead_analysis (id,organization_id,lead_id,company,email,priority,lead_score,result,created_at) VALUES (1,1,1,'Company','lead@example.com','Warm',60,'{}',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO users (id,email,password_hash,is_active,created_at,updated_at) VALUES (1,'user@example.com','hash',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO organization_memberships (id,user_id,organization_id,role,is_active,created_at,updated_at) VALUES (1,1,1,'owner',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    engine.dispose()
    command.upgrade(config, HEAD)
    engine = create_engine(settings.DATABASE_URL)
    columns = {column["name"] for column in inspect(engine).get_columns("leads")}
    assert {"processing_started_at", "processing_attempt_id"} <= columns
    with engine.connect() as connection:
        assert connection.execute(text("SELECT processing_status,processing_started_at,processing_attempt_id FROM leads WHERE id=1")).one() == ("processing", None, None)
        assert connection.scalar(text("SELECT COUNT(*) FROM lead_analysis")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM organization_memberships")) == 1
    engine.dispose()
    command.downgrade(config, PREVIOUS)
    engine = create_engine(settings.DATABASE_URL)
    columns = {column["name"] for column in inspect(engine).get_columns("leads")}
    assert "processing_started_at" not in columns and "processing_attempt_id" not in columns
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM leads")) == 1
    engine.dispose()
