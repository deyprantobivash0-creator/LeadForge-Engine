"""Real disposable persistence for the I2 caller-owned append/read boundary."""

from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import AuditEvent, Organization, User, Lead
from backend.schemas.audit_event import AuditEventReceipt, AuditValidationError
from tests.test_audit_construction import completed, user
from tests.test_audit_persistence import audit_engine  # Both metadata and Alembic fixture variants.


def _transaction(db):
    # PostgreSQL must bind disposable configuration before logger/settings import.
    from backend.database.transactions import service_transaction
    return service_transaction(db)


def _repository(db):
    from backend.repositories.audit_repository import AuditRepository
    return AuditRepository(db)


def test_append_is_provisional_caller_commits_and_read_is_immutable(audit_engine, monkeypatch):
    draft = completed()
    with Session(audit_engine) as db:
        repo = _repository(db)
        with _transaction(db):
            with monkeypatch.context() as patch:
                patch.setattr(db, "commit", lambda: pytest.fail("Repository committed"))
                receipt = repo.append(draft)
                assert type(receipt) is AuditEventReceipt
                assert receipt.event_id == draft.event_id and receipt.recorded_at.tzinfo is not None
                assert repo.get_event(1, draft.event_id) == receipt
                with Session(audit_engine) as observer:
                    assert _repository(observer).get_event(1, draft.event_id) is None
        with Session(audit_engine) as observer:
            read = _repository(observer).get_event(1, draft.event_id)
            assert read == receipt
            with pytest.raises(FrozenInstanceError):
                read.organization_id = 2
            assert not hasattr(read, "details") and not hasattr(read, "authorization_evidence")
            assert not observer.dirty and not observer.identity_map


def test_later_database_failure_rolls_back_append(audit_engine):
    draft = completed()
    with Session(audit_engine) as db:
        with pytest.raises(IntegrityError):
            with _transaction(db):
                _repository(db).append(draft)
                db.add(Organization(name=None, slug="invalid-" + uuid4().hex))
                db.flush()
        assert db.is_active
    with Session(audit_engine) as observer:
        assert _repository(observer).get_event(1, draft.event_id) is None


def test_nested_e02_scope_no_early_commit_and_outer_failure(audit_engine):
    first, second = completed(), completed()
    with Session(audit_engine) as db:
        with pytest.raises(RuntimeError, match="later failure"):
            with _transaction(db):
                _repository(db).append(first)
                with _transaction(db):
                    _repository(db).append(second)
                with Session(audit_engine) as observer:
                    assert _repository(observer).get_event(1, second.event_id) is None
                raise RuntimeError("later failure")
    with Session(audit_engine) as observer:
        for draft in (first, second):
            assert _repository(observer).get_event(1, draft.event_id) is None


def test_caught_nested_failure_preserves_e02_rollback_only(audit_engine):
    from backend.database.transactions import TransactionAborted
    draft = completed()
    with Session(audit_engine) as db:
        with pytest.raises(TransactionAborted):
            with _transaction(db):
                _repository(db).append(draft)
                try:
                    with _transaction(db):
                        raise ValueError("nested failure")
                except ValueError:
                    pass
    with Session(audit_engine) as observer:
        assert _repository(observer).get_event(1, draft.event_id) is None


def test_nested_e02_success_has_one_root_commit(audit_engine, monkeypatch):
    drafts = [completed(), completed()]
    with Session(audit_engine) as db:
        original = db.commit; commits = []
        def counted_commit():
            commits.append(True); original()
        monkeypatch.setattr(db, "commit", counted_commit)
        with _transaction(db):
            for draft in drafts:
                with _transaction(db):
                    _repository(db).append(draft)
                assert commits == []
        assert len(commits) == 1
    with Session(audit_engine) as observer:
        assert all(_repository(observer).get_event(1, d.event_id) for d in drafts)


def test_append_requires_existing_caller_service_scope(audit_engine):
    with Session(audit_engine) as db:
        with pytest.raises(AuditValidationError, match="Caller-owned"):
            _repository(db).append(completed())
        assert not db.new and not db.in_transaction()


@pytest.mark.parametrize("raw", [{}, {"organization_id": 1, "details": {}}, AuditEvent(), None])
def test_arbitrary_dict_or_orm_cannot_enter_append(audit_engine, raw):
    with Session(audit_engine) as db:
        with _transaction(db):
            with pytest.raises(AuditValidationError):
                _repository(db).append(raw)
            assert not db.new


def test_modified_builder_result_rejected_before_session_mutation(audit_engine):
    with Session(audit_engine) as db:
        with _transaction(db):
            for change in (dict(authority_role="owner"), dict(principal=user(org=2)), dict(_seal=None)):
                with pytest.raises(AuditValidationError):
                    _repository(db).append(replace(completed(), **change))
                assert not db.new


def test_cross_tenant_lookup_and_not_found_are_indistinguishable(audit_engine):
    a, b = completed(user(org=101)), completed(user(org=202))
    with Session(audit_engine) as db:
        repo = _repository(db)
        with _transaction(db):
            repo.append(a); repo.append(b)
        assert repo.get_event(101, a.event_id).event_id == a.event_id
        assert repo.get_event(202, b.event_id).event_id == b.event_id
        assert repo.get_event(202, a.event_id) is None
        assert repo.get_event(101, b.event_id) is None
        assert repo.get_event(101, str(uuid4())) is None


@pytest.mark.parametrize("org", [None, 0, -1, True, "1"])
def test_reads_require_valid_explicit_tenant(audit_engine, org):
    with Session(audit_engine) as db:
        with pytest.raises(AuditValidationError):
            _repository(db).get_event(org, str(uuid4()))
        assert not db.in_transaction()


def test_no_unscoped_read_or_history_mutation_surface(audit_engine):
    from backend.repositories.audit_repository import AuditRepository
    assert {name for name in vars(AuditRepository) if not name.startswith("_")} == {"append", "get_event"}
    with Session(audit_engine) as db:
        with pytest.raises(TypeError):
            _repository(db).get_event(str(uuid4()))
        with pytest.raises(AuditValidationError):
            _repository(db).get_event(1, "not-an-event-uuid")


@pytest.mark.parametrize("mutation", ["update", "delete"])
def test_i1_guards_remain_effective_and_session_recovers(audit_engine, mutation):
    draft = completed()
    with Session(audit_engine) as db:
        with _transaction(db):
            _repository(db).append(draft)
        row = db.scalar(select(AuditEvent).where(AuditEvent.event_id == draft.event_id))
        if mutation == "update": row.actor_id = "99"
        else: db.delete(row)
        with pytest.raises(ValueError, match="append-only"):
            db.flush()
        db.rollback()
        assert _repository(db).get_event(1, draft.event_id) is not None
        assert db.scalar(select(AuditEvent.actor_id).where(AuditEvent.event_id == draft.event_id)) == "7"
        assert db.is_active


def test_unrelated_models_still_mutate_and_history_needs_no_live_org(audit_engine):
    draft = completed(user(org=909))
    with Session(audit_engine) as db:
        repo = _repository(db)
        with _transaction(db):
            org = Organization(id=909, name="Disposable", slug="audit-i2-" + uuid4().hex)
            db.add(org); db.flush()
            lead = Lead(organization_id=909, company="Synthetic", email=uuid4().hex + "@example.invalid", source="test")
            account = User(email=uuid4().hex + "@example.invalid", password_hash="synthetic-not-a-credential")
            db.add_all([lead, account]); db.flush()
            repo.append(draft)
        with _transaction(db):
            org.name = "Updated"; lead.company = "Updated"; account.is_active = False
            db.flush()
        with _transaction(db):
            db.delete(lead); db.delete(account); db.flush(); db.delete(org)
        assert repo.get_event(909, draft.event_id) is not None


def test_duplicate_append_is_not_upsert_or_silent_replacement(audit_engine):
    draft = completed()
    with Session(audit_engine) as db:
        with _transaction(db): _repository(db).append(draft)
        with pytest.raises(IntegrityError):
            with _transaction(db): _repository(db).append(draft)
        assert _repository(db).get_event(1, draft.event_id) is not None
