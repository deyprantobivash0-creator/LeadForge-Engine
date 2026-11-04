"""Service-owned commands on an injected Session, including nested commands."""

from contextlib import contextmanager
import logging

from sqlalchemy.orm import Session

from backend.core.logger import event
from backend.database.transaction_policy import (
    GovernedRoot, current_root, service_savepoint,
)


_STATE_KEY = "leadforge.service_transaction"


class TransactionAborted(RuntimeError):
    """An inner command failed even though its caller caught the exception."""


def in_service_transaction(db: Session) -> bool:
    return current_root(db) is not None


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
    state = current_root(db)
    if state is not None:
        try:
            state.check()
            yield
        except BaseException:
            state.failed = True
            raise
        return

    state = GovernedRoot(db)
    try:
        state.start()
        yield
        if state.failed:
            raise TransactionAborted("A nested service command failed.")
        state.commit()
    except BaseException as exc:
        event("transaction.command.failed", level=logging.WARNING, exc=exc)
        try:
            state.rollback()
        except BaseException:
            state.remove()
            rollback_safely(db)
        raise
    finally:
        state.remove()
