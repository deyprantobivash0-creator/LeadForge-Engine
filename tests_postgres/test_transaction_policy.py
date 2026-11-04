"""Real-dialect TX gates using only the existing disposable PG fixture."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from backend.models import Organization, Lead
from backend.database.transaction_policy import (
    service_savepoint, require_governed_physical_root, TransactionPolicyViolation,
)


def tx(db):
    # Configuration-dependent imports must follow the guarded PG fixture.
    from backend.database.transactions import service_transaction
    return service_transaction(db)


@pytest.fixture
def tx_rows(pg_database):
    engine = create_engine(pg_database["url"], connect_args={"connect_timeout": 3,
                           "options": "-c lock_timeout=1000 -c statement_timeout=3000"}, pool_timeout=3)
    try:
        with Session(engine) as db:
            tag = uuid4().hex
            org = Organization(name="Synthetic TX", slug="tx-" + tag)
            db.add(org); db.flush()
            lead = Lead(organization_id=org.id, company="Synthetic", email=tag + "@example.invalid", source="test")
            db.add(lead); db.commit()
            ids = lead.id, org.id
        yield engine, ids
    finally:
        engine.dispose()


@pytest.mark.parametrize("settlement", ["commit", "rollback", "nested", "savepoint"])
def test_postgres_root_and_savepoint_contract(tx_rows, settlement):
    engine, (lead_id, org_id) = tx_rows
    def operation():
        with Session(engine) as db, tx(db):
            require_governed_physical_root(db)  # Must emit no SQLite BEGIN.
            if settlement == "savepoint":
                with service_savepoint(db):
                    db.execute(update(Lead).where(Lead.id == lead_id, Lead.organization_id == org_id).values(status="Lost"))
            else:
                with tx(db):
                    db.execute(update(Lead).where(Lead.id == lead_id, Lead.organization_id == org_id).values(status="Lost"))
            if settlement == "rollback":
                raise RuntimeError("Synthetic outer failure")
    if settlement == "rollback":
        with pytest.raises(RuntimeError): operation()
    else: operation()
    with Session(engine) as db:
        assert db.scalar(select(Lead.status).where(Lead.id == lead_id)) == ("New" if settlement == "rollback" else "Lost")


@pytest.mark.parametrize("attempt", ["session_commit", "session_rollback", "connection_commit", "connection_rollback", "raw", "invalidate"])
def test_postgres_policy_prevents_supported_escape(tx_rows, attempt):
    engine, (lead_id, org_id) = tx_rows
    with Session(engine) as db:
        with pytest.raises(TransactionPolicyViolation):
            with tx(db):
                db.execute(update(Lead).where(Lead.id == lead_id, Lead.organization_id == org_id).values(status="Lost"))
                if attempt == "raw": db.connection().exec_driver_sql("COMMIT")
                elif attempt == "invalidate":
                    db.connection().invalidate(); db.scalar(select(Lead.id))
                else:
                    scope, method = attempt.split("_")
                    getattr(db if scope == "session" else db.connection(), method)()
    with Session(engine) as db:
        assert db.scalar(select(Lead.status).where(Lead.id == lead_id)) == "New"
