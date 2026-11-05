"""P1 repository ownership only; all databases disposable, no audit integration."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import InvalidRequestError, OperationalError
from sqlalchemy.orm import Session

from backend.database.base import Base
from backend.models import Lead, Organization
from backend.repositories.lead_repository import LeadRepository
from backend.database.transaction_policy import (
    TransactionPolicyViolation, require_governed_physical_root, service_savepoint,
)


@pytest.fixture
def locking_engine(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "locking.db").as_posix(),
                           connect_args={"timeout": 0})
    Base.metadata.create_all(engine)
    with Session(engine) as db, transaction(db):
        db.add_all([Organization(id=1, name="One", slug="one"),
                    Organization(id=2, name="Two", slug="two")])
        db.flush()
        db.add_all([
            Lead(id=1, organization_id=1, company="Synthetic",
                 email="locking@example.invalid", source="test", status="New"),
            Lead(id=2, organization_id=2, company="Other tenant",
                 email="other@example.invalid", source="test", status="New"),
        ])
    try:
        yield engine
    finally:
        engine.dispose()


def transaction(db):
    from backend.database.transactions import service_transaction
    return service_transaction(db)


def status(engine):
    with Session(engine) as observer:
        return observer.scalar(select(Lead.status).where(Lead.id == 1))


@pytest.mark.parametrize("tenant,lead_id,found", [(1, 1, True), (2, 1, False), (1, 999, False)])
def test_scoped_acquisition(locking_engine, tenant, lead_id, found):
    with Session(locking_engine) as db, transaction(db):
        lead = LeadRepository(db).get_lead_for_lifecycle_update(lead_id, tenant)
        assert (lead is not None) is found
        if lead is not None:
            assert lead.id == lead_id and lead.organization_id == tenant


def test_stale_identity_map_refresh_and_autobegin(locking_engine):
    with Session(locking_engine) as reader, Session(locking_engine) as writer:
        repo = LeadRepository(reader)
        cached = repo.get_lead_by_id(1, 1)
        with transaction(writer):
            writer.get(Lead, 1).status = "Qualified"
        assert repo.get_lead_by_id(1, 1) is cached and cached.status == "New"
        assert reader.in_transaction()  # SQLAlchemy autobegin precedes E02.
        with transaction(reader):
            owned = repo.get_lead_for_lifecycle_update(1, 1)
            assert owned is cached and owned.status == "Qualified"
            owned.status = "Contacted"
            reader.flush()
        assert status(locking_engine) == "Contacted"


def test_sqlite_ownership_precedes_select_and_blocks_writer(locking_engine):
    statements = []
    def observe(_connection, _cursor, statement, *_args):
        statements.append(statement)
    attempted = Event()
    def competitor():
        with Session(locking_engine) as other:
            attempted.set()
            with transaction(other):
                LeadRepository(other).update_lifecycle(1, 1, status="Lost")
    with Session(locking_engine) as db:
        event.listen(locking_engine, "before_cursor_execute", observe)
        try:
            with transaction(db):
                lead = LeadRepository(db).get_lead_for_lifecycle_update(1, 1)
                business = [sql for sql in statements if sql != "BEGIN"]
                assert business[0].startswith("UPDATE leads SET id=leads.id WHERE")
                assert "organization_id" in business[0] and business[1].startswith("SELECT")
                assert statements.count("BEGIN") == 1  # Established by central E02.
                event.remove(locking_engine, "before_cursor_execute", observe)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(competitor)
                    assert attempted.wait(2)
                    with pytest.raises(OperationalError):
                        future.result(timeout=5)
                assert status(locking_engine) == "New"
                lead.status = "Qualified"
                db.flush()
        finally:
            if event.contains(locking_engine, "before_cursor_execute", observe):
                event.remove(locking_engine, "before_cursor_execute", observe)
    assert status(locking_engine) == "Qualified"
    with Session(locking_engine) as other, transaction(other):
        LeadRepository(other).get_lead_for_lifecycle_update(1, 1).status = "Contacted"
    assert status(locking_engine) == "Contacted"  # Ownership released at root settlement.


def test_repository_never_settles_and_root_rollback_restores(locking_engine):
    settlements = []
    def committed(connection): settlements.append("commit")
    def rolled_back(connection): settlements.append("rollback")
    event.listen(locking_engine, "commit", committed)
    event.listen(locking_engine, "rollback", rolled_back)
    try:
        with Session(locking_engine) as db:
            with pytest.raises(RuntimeError, match="outer"):
                with transaction(db):
                    lead = LeadRepository(db).get_lead_for_lifecycle_update(1, 1)
                    lead.status = "Lost"
                    db.flush()
                    assert settlements == []
                    raise RuntimeError("outer")
        assert settlements == ["rollback"]
    finally:
        event.remove(locking_engine, "commit", committed)
        event.remove(locking_engine, "rollback", rolled_back)
    assert status(locking_engine) == "New"


@pytest.mark.parametrize("fail", [False, True])
def test_nested_e02_has_one_root_settlement(locking_engine, fail):
    from backend.database.transactions import TransactionAborted
    with Session(locking_engine) as db:
        commits = []
        def counted(connection):
            commits.append(True)
        event.listen(locking_engine, "commit", counted)
        def operation():
            with transaction(db):
                with transaction(db):
                    lead = LeadRepository(db).get_lead_for_lifecycle_update(1, 1)
                    lead.status = "Qualified"
                    db.flush()
                assert commits == []
                if fail:
                    try:
                        with transaction(db):
                            raise ValueError("nested")
                    except ValueError:
                        pass
        try:
            if fail:
                with pytest.raises(TransactionAborted):
                    operation()
            else:
                operation()
            assert len(commits) == (0 if fail else 1)
        finally:
            event.remove(locking_engine, "commit", counted)
    assert status(locking_engine) == ("New" if fail else "Qualified")


def test_competing_owner_failure_rolls_back_without_stale_result(locking_engine):
    with Session(locking_engine) as owner, Session(locking_engine) as contender:
        cached = LeadRepository(contender).get_lead_by_id(1, 1)
        with transaction(owner):
            LeadRepository(owner).get_lead_for_lifecycle_update(1, 1).status = "Qualified"
            owner.flush()
            with pytest.raises(OperationalError):
                with transaction(contender):
                    LeadRepository(contender).get_lead_for_lifecycle_update(1, 1)
            assert not contender.in_transaction()
        with transaction(contender):
            assert LeadRepository(contender).get_lead_for_lifecycle_update(1, 1).status == "Qualified"
        assert cached.status == "Qualified"


def test_requires_caller_scope_without_sql(locking_engine):
    with Session(locking_engine) as db:
        with pytest.raises(TransactionPolicyViolation, match="Caller-owned"):
            LeadRepository(db).get_lead_for_lifecycle_update(1, 1)
        assert not db.in_transaction()


def test_existing_sqlite_read_snapshot_fails_closed_then_can_retry(locking_engine):
    with locking_engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    with Session(locking_engine) as reader, Session(locking_engine) as writer:
        with pytest.raises(OperationalError) as rejected:
            with transaction(reader):
                # Establish the read snapshot through the approved E02 API.
                require_governed_physical_root(reader)
                cached = LeadRepository(reader).get_lead_by_id(1, 1)
                assert cached.status == "New"
                with transaction(writer):
                    writer.get(Lead, 1).status = "Qualified"
                LeadRepository(reader).get_lead_for_lifecycle_update(1, 1)
        assert getattr(rejected.value.orig, "sqlite_errorname", None) == "SQLITE_BUSY_SNAPSHOT"
        assert not reader.in_transaction() and status(locking_engine) == "Qualified"
        with transaction(reader):
            assert LeadRepository(reader).get_lead_for_lifecycle_update(1, 1).status == "Qualified"


def test_pending_changes_are_not_discarded_or_autoflushed(locking_engine):
    with Session(locking_engine) as db:
        lead = db.get(Lead, 1)
        with pytest.raises(InvalidRequestError, match="Flush pending"):
            with transaction(db):
                lead.notes = "Synthetic pending change"
                LeadRepository(db).get_lead_for_lifecycle_update(1, 1)
    assert status(locking_engine) == "New"
    with Session(locking_engine) as observer:
        assert observer.get(Lead, 1).notes is None


def test_real_savepoint_is_rejected_without_independent_settlement(locking_engine):
    with Session(locking_engine) as db, transaction(db):
        with service_savepoint(db):
            with pytest.raises(InvalidRequestError, match="savepoint"):
                LeadRepository(db).get_lead_for_lifecycle_update(1, 1)
        assert db.in_transaction()


def test_autocommit_mode_fails_before_accepting_a_snapshot(locking_engine):
    autocommit = locking_engine.execution_options(isolation_level="AUTOCOMMIT")
    with Session(autocommit) as db:
        with pytest.raises(TransactionPolicyViolation):
            with transaction(db):
                LeadRepository(db).get_lead_for_lifecycle_update(1, 1)
    assert status(locking_engine) == "New"


def test_existing_lifecycle_and_read_behavior_unchanged(locking_engine):
    when = datetime(2026, 10, 14, 12)
    with Session(locking_engine) as db:
        repo = LeadRepository(db)
        assert repo.get_lead_by_id(1, 2) is None
        with transaction(db):
            lead = repo.update_lifecycle(1, 1, status="Contacted", notes="Synthetic",
                                         last_contacted=when, next_follow_up=when)
            assert lead.status == "Contacted" and lead.notes == "Synthetic"
            assert repo.update_lifecycle(1, 1, status="Contacted").notes == "Synthetic"
            assert lead.last_contacted == lead.next_follow_up == when
            assert repo.update_lifecycle(999, 1, status="Lost") is None


def test_poisoned_e02_cannot_acquire_an_authoritative_row(locking_engine):
    from backend.database.transactions import TransactionAborted

    with Session(locking_engine) as db:
        with pytest.raises(TransactionAborted):
            with transaction(db):
                LeadRepository(db).get_lead_for_lifecycle_update(1, 1)
                with pytest.raises(TransactionPolicyViolation):
                    db.commit()
                with pytest.raises(TransactionPolicyViolation):
                    LeadRepository(db).get_lead_for_lifecycle_update(1, 1)
    assert status(locking_engine) == "New"


@pytest.mark.parametrize("initial_binding", [False, True])
@pytest.mark.parametrize("active", [False, True])
def test_foreign_ownership_cannot_authorize_acquisition(locking_engine, initial_binding, active):
    # Deliberately hostile external ownership, outside the supported E02 path.
    with locking_engine.connect() as foreign:
        if active:
            foreign.begin()
        foreign_root = foreign.get_transaction()
        statements = []
        def observe(*args): statements.append(True)
        event.listen(foreign, "before_cursor_execute", observe)
        try:
            with Session(foreign if initial_binding else locking_engine) as db:
                with pytest.raises(TransactionPolicyViolation):
                    with transaction(db):
                        if not initial_binding:
                            db.bind = foreign
                        LeadRepository(db).get_lead_for_lifecycle_update(1, 1)
            assert statements == []
            assert foreign.get_transaction() is foreign_root
        finally:
            event.remove(foreign, "before_cursor_execute", observe)


@pytest.mark.parametrize("autoflush", [False, True])
@pytest.mark.parametrize("pending", ["new", "dirty", "deleted"])
def test_pending_state_is_retained_without_business_sql(locking_engine, autoflush, pending):
    with Session(locking_engine, autoflush=autoflush) as db:
        other = db.get(Lead, 2) if pending != "new" else Lead(
            organization_id=1, company=None, email="invalid@example.invalid", source="test",
        )
        with pytest.raises(RuntimeError, match="caller abort"):
            with transaction(db):
                if pending == "new":
                    db.add(other)  # Autoflush would raise NOT NULL IntegrityError.
                elif pending == "dirty":
                    other.notes = "must not be discarded"
                else:
                    db.delete(other)
                statements = []
                def observe(_conn, _cursor, sql, *_args): statements.append(sql)
                event.listen(locking_engine, "before_cursor_execute", observe)
                try:
                    with pytest.raises(InvalidRequestError, match="Flush pending"):
                        LeadRepository(db).get_lead_for_lifecycle_update(1, 1)
                finally:
                    event.remove(locking_engine, "before_cursor_execute", observe)
                assert db.autoflush is autoflush
                assert other in getattr(db, pending)
                if pending == "dirty":
                    assert other.notes == "must not be discarded"
                assert not any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                               for sql in statements)
                raise RuntimeError("caller abort")
    with Session(locking_engine) as observer:
        assert observer.get(Lead, 2).notes is None
        assert observer.scalar(select(Lead.id).where(Lead.email == "invalid@example.invalid")) is None


@pytest.mark.parametrize("lead_id,tenant,rowcount", [(1, 1, 1), (1, 2, 0), (999, 1, 0)])
def test_sqlite_writer_noop_preserves_every_persisted_value(locking_engine, lead_id, tenant, rowcount):
    with Session(locking_engine) as seed, transaction(seed):
        lead = seed.get(Lead, 1)
        lead.notes = "before-image"
        lead.last_contacted = lead.next_follow_up = datetime(2026, 10, 14, 12)
        lead.lead_score, lead.priority = 42, "Warm"
    with locking_engine.connect() as schema:
        assert schema.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='leads'"
        ).all() == []
    with Session(locking_engine) as observer:
        before = observer.execute(select(Lead.__table__).order_by(Lead.id)).all()
    updates = []
    def executed(_conn, cursor, sql, *_args):
        if sql.startswith("UPDATE leads"):
            updates.append((sql, cursor.rowcount))
    event.listen(locking_engine, "after_cursor_execute", executed)
    try:
        with Session(locking_engine) as db, transaction(db):
            owned = LeadRepository(db).get_lead_for_lifecycle_update(lead_id, tenant)
            assert (owned is not None) is bool(rowcount)
            if owned is not None:
                assert owned.status == "New" and owned.notes == "before-image"
    finally:
        event.remove(locking_engine, "after_cursor_execute", executed)
    assert len(updates) == 1 and updates[0][1] == rowcount
    assert "SET id=leads.id WHERE" in updates[0][0]
    with Session(locking_engine) as observer:
        assert observer.execute(select(Lead.__table__).order_by(Lead.id)).all() == before


@pytest.mark.parametrize("rollback", [False, True], ids=["owner_commit", "owner_rollback"])
def test_two_session_before_image_after_failed_writer_acquisition(locking_engine, rollback):
    failed, settled = Event(), Event()

    def contender():
        with Session(locking_engine) as db:
            repo = LeadRepository(db)
            cached = repo.get_lead_by_id(1, 1)
            original = cached.status
            with pytest.raises(OperationalError) as caught:
                with transaction(db):
                    repo.get_lead_for_lifecycle_update(1, 1)
            assert getattr(caught.value.orig, "sqlite_errorname", None) == "SQLITE_BUSY"
            failed.set()
            assert settled.wait(5), "Owner did not settle within the test budget"
            with transaction(db):
                owned = repo.get_lead_for_lifecycle_update(1, 1)
                return original, owned.status, owned is cached

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = None
        try:
            with Session(locking_engine) as owner:
                def operation():
                    nonlocal future
                    with transaction(owner):
                        owned = LeadRepository(owner).get_lead_for_lifecycle_update(1, 1)
                        assert owned.status == "New"
                        owned.status = "Qualified"
                        owner.flush()
                        future = pool.submit(contender)
                        if not failed.wait(3):
                            future.result(timeout=1)
                            pytest.fail("Competing acquisition did not report writer contention")
                        if rollback:
                            raise RuntimeError("owner rollback")
                if rollback:
                    with pytest.raises(RuntimeError, match="owner rollback"):
                        operation()
                else:
                    operation()
        finally:
            settled.set()
        assert future.result(timeout=8) == ("New", "New" if rollback else "Qualified", True)
