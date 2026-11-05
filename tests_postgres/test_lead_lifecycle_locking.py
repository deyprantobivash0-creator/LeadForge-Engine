"""P1 real row ownership using only the guarded disposable PostgreSQL fixture."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import DBAPIError, InvalidRequestError
from sqlalchemy.orm import Session

from backend.models import Lead, Organization
from backend.repositories.lead_repository import LeadRepository
from backend.database.transaction_policy import TransactionPolicyViolation, service_savepoint


@pytest.fixture
def locking_rows(pg_database):
    engine = create_engine(pg_database["url"], connect_args={"connect_timeout": 3,
                           "options": "-c lock_timeout=5000 -c statement_timeout=8000"}, pool_timeout=3)
    suffix = uuid4().hex
    with Session(engine) as db, transaction(db):
        org = Organization(name="P1 owned", slug="p1-owned-" + suffix)
        other = Organization(name="P1 foreign", slug="p1-foreign-" + suffix)
        db.add_all([org, other])
        db.flush()
        lead = Lead(organization_id=org.id, company="Synthetic",
                    email=suffix + "@example.invalid", source="test", status="New")
        db.add(lead)
        db.add_all([
            Lead(organization_id=org.id, company="Other owned", email="other-" + suffix + "@example.invalid", source="test"),
            Lead(organization_id=other.id, company="Other tenant", email=suffix + "@example.invalid", source="test"),
        ])
        db.flush()
        ids = lead.id, org.id, other.id
    try:
        yield engine, ids
    finally:
        engine.dispose()


def transaction(db):
    from backend.database.transactions import service_transaction
    return service_transaction(db)


def read_status(engine, lead_id):
    with Session(engine) as db:
        return db.scalar(select(Lead.status).where(Lead.id == lead_id))


def test_postgres_owned_and_missing(locking_rows):
    engine, (lead_id, org_id, _) = locking_rows
    with Session(engine) as db, transaction(db):
        lead = LeadRepository(db).get_lead_for_lifecycle_update(lead_id, org_id)
        assert lead.id == lead_id and lead.organization_id == org_id
        assert LeadRepository(db).get_lead_for_lifecycle_update(-1, org_id) is None


def test_postgres_foreign_lookup_does_not_lock_owned_row(locking_rows):
    engine, (lead_id, org_id, foreign_id) = locking_rows
    def writer():
        with Session(engine) as db, transaction(db):
            LeadRepository(db).get_lead_for_lifecycle_update(lead_id, org_id).status = "Qualified"
    with Session(engine) as db, transaction(db):
        assert LeadRepository(db).get_lead_for_lifecycle_update(lead_id, foreign_id) is None
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(writer).result(timeout=5)
    assert read_status(engine, lead_id) == "Qualified"


def test_postgres_stale_identity_map_refreshed_before_mutation(locking_rows):
    engine, (lead_id, org_id, _) = locking_rows
    with Session(engine) as reader, Session(engine) as writer:
        repo = LeadRepository(reader)
        cached = repo.get_lead_by_id(lead_id, org_id)
        with transaction(writer):
            writer.get(Lead, lead_id).status = "Qualified"
        assert repo.get_lead_by_id(lead_id, org_id) is cached and cached.status == "New"
        with transaction(reader):
            owned = repo.get_lead_for_lifecycle_update(lead_id, org_id)
            assert owned is cached and owned.status == "Qualified"
            owned.status = "Contacted"
            reader.flush()
    assert read_status(engine, lead_id) == "Contacted"


def test_postgres_owner_prevents_conflicting_settlement(locking_rows):
    engine, (lead_id, org_id, _) = locking_rows
    competitor_engine = create_engine(engine.url, connect_args={"connect_timeout": 3,
                                      "options": "-c lock_timeout=250 -c statement_timeout=2000"}, pool_timeout=3)
    attempted = Event()
    def blocked_writer():
        with Session(competitor_engine) as db:
            try:
                with transaction(db):
                    pid = db.scalar(select(func.pg_backend_pid()))
                    attempted.set()
                    LeadRepository(db).get_lead_for_lifecycle_update(lead_id, org_id).status = "Lost"
            except DBAPIError as exc:
                assert getattr(exc.orig, "sqlstate", None) == "55P03"
                return pid
            raise AssertionError("Competing writer settled before the owner")
    try:
        with Session(engine) as owner, transaction(owner):
            lead = LeadRepository(owner).get_lead_for_lifecycle_update(lead_id, org_id)
            owner_pid = owner.scalar(select(func.pg_backend_pid()))
            assert lead.status == "New"
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(blocked_writer)
                assert attempted.wait(3)
                assert future.result(timeout=5) != owner_pid
            assert read_status(engine, lead_id) == "New"
            lead.status = "Qualified"
            owner.flush()
    finally:
        competitor_engine.dispose()
    assert read_status(engine, lead_id) == "Qualified"
    with Session(engine) as writer, transaction(writer):
        lead = LeadRepository(writer).get_lead_for_lifecycle_update(lead_id, org_id)
        assert lead.status == "Qualified"
        lead.status = "Contacted"
    assert read_status(engine, lead_id) == "Contacted"


def test_postgres_outer_rollback_releases_lock_and_restores_state(locking_rows):
    engine, (lead_id, org_id, _) = locking_rows
    with Session(engine) as owner:
        with pytest.raises(RuntimeError, match="outer"):
            with transaction(owner):
                with transaction(owner):
                    LeadRepository(owner).get_lead_for_lifecycle_update(lead_id, org_id).status = "Lost"
                    owner.flush()
                raise RuntimeError("outer")
    assert read_status(engine, lead_id) == "New"
    with Session(engine) as writer, transaction(writer):
        assert LeadRepository(writer).get_lead_for_lifecycle_update(lead_id, org_id).status == "New"


def wait_for_row_lock(engine, blocked_pid, owner_pid, future):
    """Observe an actual server-side wait, rather than guessing from elapsed time."""
    deadline = monotonic() + 3
    poll = Event()
    with Session(engine) as observer:
        while monotonic() < deadline:
            blockers = observer.scalar(select(func.pg_blocking_pids(blocked_pid)))
            if owner_pid in blockers:
                assert not future.done(), "Contender finished before owner settlement"
                return
            if future.done():
                future.result(timeout=0)
                pytest.fail("Competing acquisition returned without waiting for its owner")
            poll.wait(0.01)
    pytest.fail(f"No server-side lock wait observed for contender {blocked_pid} on owner {owner_pid}")


@pytest.mark.parametrize("rollback", [False, True], ids=["owner_commit", "owner_rollback"])
def test_postgres_waiting_acquisition_refreshes_before_image(locking_rows, rollback):
    engine, (lead_id, org_id, _) = locking_rows
    ready, contender_pids = Event(), []

    def contender():
        with Session(engine) as db, transaction(db):
            repo = LeadRepository(db)
            cached = repo.get_lead_by_id(lead_id, org_id)
            original = cached.status
            pid = db.scalar(select(func.pg_backend_pid()))
            contender_pids.append(pid)
            ready.set()
            owned = repo.get_lead_for_lifecycle_update(lead_id, org_id)
            return original, owned.status, owned is cached, pid

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = None
        with Session(engine) as owner:
            def operation():
                nonlocal future
                with transaction(owner):
                    lead = LeadRepository(owner).get_lead_for_lifecycle_update(lead_id, org_id)
                    assert lead.status == "New"
                    owner_pid = owner.scalar(select(func.pg_backend_pid()))
                    lead.status = "Qualified"
                    owner.flush()
                    future = pool.submit(contender)
                    assert ready.wait(3), "Contender did not reach acquisition"
                    assert contender_pids[0] != owner_pid
                    wait_for_row_lock(engine, contender_pids[0], owner_pid, future)
                    if rollback:
                        raise RuntimeError("owner rollback")
            if rollback:
                with pytest.raises(RuntimeError, match="owner rollback"):
                    operation()
            else:
                operation()
        initial, acquired, same_object, _pid = future.result(timeout=10)
    expected = "New" if rollback else "Qualified"
    assert (initial, acquired, same_object) == ("New", expected, True)
    assert read_status(engine, lead_id) == expected


@pytest.mark.parametrize("foreign_tenant", [False, True], ids=["same_tenant_other_row", "other_tenant"])
def test_postgres_lock_does_not_amplify_to_other_rows(locking_rows, foreign_tenant):
    engine, (lead_id, org_id, other_org) = locking_rows
    target_org = other_org if foreign_tenant else org_id
    with Session(engine) as setup:
        other_id = setup.scalar(select(Lead.id).where(Lead.organization_id == target_org, Lead.id != lead_id))

    def writer():
        with Session(engine) as db, transaction(db):
            other = LeadRepository(db).get_lead_for_lifecycle_update(other_id, target_org)
            other.status = "Qualified"

    with Session(engine) as owner, transaction(owner):
        assert LeadRepository(owner).get_lead_for_lifecycle_update(lead_id, org_id).status == "New"
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(writer).result(timeout=5)
    assert read_status(engine, other_id) == "Qualified"
    assert read_status(engine, lead_id) == "New"


def test_postgres_acquisition_is_one_scoped_locked_select(locking_rows):
    engine, (lead_id, org_id, _) = locking_rows
    statements = []
    def observe(_conn, _cursor, sql, *_args): statements.append(sql)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        with Session(engine) as db, transaction(db):
            assert LeadRepository(db).get_lead_for_lifecycle_update(lead_id, org_id).status == "New"
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert len(statements) == 1
    sql = statements[0].upper()
    assert sql.startswith("SELECT") and "FOR UPDATE OF LEADS" in sql
    predicate = sql.split("WHERE", 1)[1]
    assert "LEADS.ID =" in predicate and "LEADS.ORGANIZATION_ID =" in predicate


@pytest.mark.parametrize("autoflush", [False, True])
@pytest.mark.parametrize("pending", ["new", "dirty", "deleted"])
def test_postgres_pending_state_cannot_contaminate_acquisition(locking_rows, autoflush, pending):
    engine, (lead_id, org_id, _) = locking_rows
    with Session(engine, autoflush=autoflush) as db:
        lead = db.get(Lead, lead_id) if pending != "new" else Lead(
            organization_id=org_id, company=None, email="invalid@example.invalid", source="test",
        )
        with pytest.raises(RuntimeError, match="caller abort"):
            with transaction(db):
                if pending == "new": db.add(lead)
                elif pending == "dirty": lead.notes = "must not be discarded"
                else: db.delete(lead)
                statements = []
                def observe(_conn, _cursor, sql, *_args): statements.append(sql)
                event.listen(engine, "before_cursor_execute", observe)
                try:
                    with pytest.raises(InvalidRequestError, match="Flush pending"):
                        LeadRepository(db).get_lead_for_lifecycle_update(lead_id, org_id)
                finally:
                    event.remove(engine, "before_cursor_execute", observe)
                assert lead in getattr(db, pending) and db.autoflush is autoflush
                if pending == "dirty": assert lead.notes == "must not be discarded"
                assert not any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for sql in statements)
                raise RuntimeError("caller abort")
    with Session(engine) as observer:
        assert observer.get(Lead, lead_id).notes is None
        assert observer.scalar(select(Lead.id).where(Lead.organization_id == org_id, Lead.email == "invalid@example.invalid")) is None


def test_postgres_requires_a_governed_root(locking_rows):
    engine, (lead_id, org_id, _) = locking_rows
    statements = []
    def observe(*args): statements.append(True)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        with Session(engine) as db:
            with pytest.raises(TransactionPolicyViolation, match="Caller-owned"):
                LeadRepository(db).get_lead_for_lifecycle_update(lead_id, org_id)
        assert statements == []
    finally:
        event.remove(engine, "before_cursor_execute", observe)


def test_postgres_poisoned_root_cannot_acquire(locking_rows):
    from backend.database.transactions import TransactionAborted
    engine, (lead_id, org_id, _) = locking_rows
    with Session(engine) as db:
        with pytest.raises(TransactionAborted):
            with transaction(db):
                LeadRepository(db).get_lead_for_lifecycle_update(lead_id, org_id)
                with pytest.raises(TransactionPolicyViolation): db.commit()
                with pytest.raises(TransactionPolicyViolation):
                    LeadRepository(db).get_lead_for_lifecycle_update(lead_id, org_id)
    assert read_status(engine, lead_id) == "New"


def test_postgres_approved_savepoint_cannot_shorten_acquisition_lock_lifetime(locking_rows):
    engine, (lead_id, org_id, _) = locking_rows
    with Session(engine) as db, transaction(db):
        with service_savepoint(db):
            with pytest.raises(InvalidRequestError, match="savepoint"):
                LeadRepository(db).get_lead_for_lifecycle_update(lead_id, org_id)
        assert LeadRepository(db).get_lead_for_lifecycle_update(lead_id, org_id).status == "New"


@pytest.mark.parametrize("initial_binding", [False, True])
def test_postgres_foreign_transaction_cannot_authorize_acquisition(locking_rows, initial_binding):
    engine, (lead_id, org_id, _) = locking_rows
    # Hostile external setup is deliberately outside E02's supported API.
    with engine.connect() as foreign:
        foreign_root = foreign.begin()
        statements = []
        def observe(*args): statements.append(True)
        event.listen(foreign, "before_cursor_execute", observe)
        try:
            with Session(foreign if initial_binding else engine) as db:
                with pytest.raises(TransactionPolicyViolation):
                    with transaction(db):
                        if not initial_binding: db.bind = foreign
                        LeadRepository(db).get_lead_for_lifecycle_update(lead_id, org_id)
            assert statements == [] and foreign.get_transaction() is foreign_root
        finally:
            event.remove(foreign, "before_cursor_execute", observe)
