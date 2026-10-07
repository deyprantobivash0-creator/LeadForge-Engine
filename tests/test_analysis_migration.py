"""Disposable SQLite checks for the Step 3C revision."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.core.config import settings


PREVIOUS = "c3b2a1d0e9f8"
HEAD = "d4c3b2a1e0f9"
ROOT = Path(__file__).resolve().parents[1]


def test_populated_upgrade_backfill_and_downgrade(tmp_path, monkeypatch):
    db_path = tmp_path / "analysis.db"
    assert db_path.parent.name.startswith("test_")
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, PREVIOUS)
    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as connection:
        for org_id in (1, 2):
            connection.execute(text("INSERT INTO organizations (id,name,slug,plan,monthly_lead_limit,is_active,created_at) VALUES (:id,:name,:slug,'standard',500,1,CURRENT_TIMESTAMP)"), {"id": org_id, "name": f"Org {org_id}", "slug": f"org-{org_id}"})
            connection.execute(text("INSERT INTO leads (id,organization_id,company,email,source,status,created_at) VALUES (:id,:org,'Co','shared@example.com','test','New',CURRENT_TIMESTAMP)"), {"id": org_id + 10, "org": org_id})
            connection.execute(text("INSERT INTO lead_analysis (id,organization_id,company,email,priority,lead_score,result,created_at) VALUES (:id,:org,'Co','shared@example.com','Hot',80,'{}',CURRENT_TIMESTAMP)"), {"id": org_id + 20, "org": org_id})
        connection.execute(text("INSERT INTO lead_analysis (id,organization_id,company,email,priority,lead_score,result,created_at) VALUES (30,1,'Missing','missing@example.com','Cold',20,'{}',CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO users (id,email,password_hash,is_active,created_at,updated_at) VALUES (1,'user@example.com','test-hash',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO organization_memberships (id,user_id,organization_id,role,is_active,created_at,updated_at) VALUES (1,1,1,'owner',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO auth_sessions (id,user_id,token_hash,csrf_token_hash,created_at,expires_at,last_seen_at) VALUES (1,1,'token','csrf',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    engine.dispose()
    command.upgrade(config, HEAD)
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id,lead_id FROM lead_analysis ORDER BY id")).all() == [(21, 11), (22, 12), (30, None)]
        assert connection.scalar(text("SELECT COUNT(*) FROM auth_sessions")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM organization_memberships")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM leads")) == 2
    engine.dispose()
    command.downgrade(config, PREVIOUS)
    engine = create_engine(settings.DATABASE_URL)
    assert "lead_id" not in {column["name"] for column in inspect(engine).get_columns("lead_analysis")}
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM lead_analysis")) == 3
    engine.dispose()
