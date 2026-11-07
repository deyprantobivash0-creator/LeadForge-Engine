from collections.abc import Generator

from sqlalchemy import event
from sqlalchemy.orm import Session

from backend.database.session import SessionLocal


_AUDIT_CONNECTIONS = "leadforge.audit.canonical_connections"


def canonical_audit_connections(db):
    """Already-open request connections, not an audit operation or authority.

    G0 alone reads their trusted endpoint metadata. This getter never acquires
    a connection, resolves a hostname, or touches native driver state.
    """
    return tuple(db.info.get(_AUDIT_CONNECTIONS, ()))


def get_db() -> Generator:
    db = SessionLocal()
    connections = []
    observing = False

    def canonical_started(_db, transaction, connection):
        if transaction.parent is None:
            connections[:] = [connection]

    try:
        if isinstance(db, Session):
            db.info[_AUDIT_CONNECTIONS] = connections
            event.listen(db, "after_begin", canonical_started)
            observing = True
        yield db
    finally:
        try:
            if observing:
                event.remove(db, "after_begin", canonical_started)
        finally:
            if isinstance(db, Session):
                db.info.pop(_AUDIT_CONNECTIONS, None)
            db.close()
