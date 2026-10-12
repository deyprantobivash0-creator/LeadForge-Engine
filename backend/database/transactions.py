"""Service-owned commands on an injected Session, including nested commands."""

from contextlib import contextmanager
import logging

from sqlalchemy.orm import Session

from backend.core.logger import event


_STATE_KEY = "leadforge.service_transaction"


class TransactionAborted(RuntimeError):
    """An inner command failed even though its caller caught the exception."""


def in_service_transaction(db: Session) -> bool:
    return _STATE_KEY in db.info


def rollback_safely(db: Session) -> None:
    """Preserve the original error; callers should discard a failed operation Session."""
    try:
        db.rollback()
    except Exception as exc:
        event("transaction.rollback.failed", level=logging.ERROR, exc=exc)
        # Invalidate rather than allow another command on a broken connection.
        try:
            db.invalidate()
        except Exception as invalidate_error:
            event("transaction.invalidate.failed", level=logging.ERROR, exc=invalidate_error)


@contextmanager
def service_transaction(db: Session):
    """Join an outer service command; only the outermost scope commits/rolls back.

    A Session may already have an autobegun transaction from authorization reads.
    The command adopts it. Callers must not commit/rollback inside this scope or
    mix it with a separately owned Session.begin() transaction.
    """
    state = db.info.get(_STATE_KEY)
    if state is not None:
        try:
            yield
        except BaseException:
            state["failed"] = True
            raise
        return

    state = {"failed": False}
    db.info[_STATE_KEY] = state
    try:
        yield
        if state["failed"]:
            raise TransactionAborted("A nested service command failed.")
        db.commit()
    except BaseException as exc:
        event("transaction.command.failed", level=logging.WARNING, exc=exc)
        rollback_safely(db)
        raise
    finally:
        db.info.pop(_STATE_KEY, None)
