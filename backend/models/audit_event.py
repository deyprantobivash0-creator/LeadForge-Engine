"""E05 persistence only: historical snapshots, not an authority or event builder."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, JSON, SmallInteger, String, event
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from backend.database.base import Base


class AuditUTCDateTime(TypeDecorator):
    """Audit-local aware UTC API; SQLite stores naive UTC, PostgreSQL TIMESTAMPTZ."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Audit timestamps require aware datetime values.")
        value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            if dialect.name != "sqlite":
                raise ValueError("Audit timestamp storage returned a naive value.")
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    # UUID allocation is the sole model default; context/times/version are explicit.
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(AuditUTCDateTime(), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(AuditUTCDateTime(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(48), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    delegated_by_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    delegated_by_actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    integration_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Shape/enums/cardinality/bytes/secrets are I2 builder responsibilities.
    authorization_evidence: Mapped[list[dict]] = mapped_column(JSON(none_as_null=True), nullable=False)
    authority_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    details: Mapped[dict] = mapped_column(JSON(none_as_null=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('business.command.completed','permission.denied','security.command.rejected') "
            "AND action IN ('lead.create','lead.lifecycle.change','lead.import') "
            "AND outcome IN ('SUCCEEDED','DENIED') "
            "AND reason_code IN ('COMMAND_COMPLETED','ACTION_PERMISSION_DENIED','EXECUTION_TENANT_MISMATCH') "
            "AND principal_type IN ('USER','SYSTEM','AGENT','WORKFLOW','INTEGRATION') "
            "AND (delegated_by_type IS NULL OR delegated_by_type IN ('USER','SYSTEM','AGENT','WORKFLOW','INTEGRATION')) "
            "AND target_type IN ('lead','lead_import') "
            "AND (authority_role IS NULL OR authority_role IN ('owner','admin','member'))",
            name="domains",
        ),
        CheckConstraint(
            "(event_type = 'business.command.completed' AND outcome = 'SUCCEEDED' AND reason_code = 'COMMAND_COMPLETED') "
            "OR (event_type = 'permission.denied' AND outcome = 'DENIED' AND reason_code = 'ACTION_PERMISSION_DENIED') "
            "OR (event_type = 'security.command.rejected' AND outcome = 'DENIED' AND reason_code = 'EXECUTION_TENANT_MISMATCH')",
            name="event_outcome",
        ),
        CheckConstraint("organization_id > 0", name="tenant_positive"),
        CheckConstraint(
            "length(event_id) = 36 AND length(event_type) BETWEEN 1 AND 64 "
            "AND length(action) BETWEEN 1 AND 64 AND length(outcome) BETWEEN 1 AND 16 "
            "AND length(reason_code) BETWEEN 1 AND 48 AND length(principal_type) BETWEEN 1 AND 16 "
            "AND length(actor_id) BETWEEN 1 AND 128 AND length(correlation_id) BETWEEN 1 AND 64 "
            "AND length(target_type) BETWEEN 1 AND 32 AND schema_version = 1 "
            "AND (delegated_by_type IS NULL OR length(delegated_by_type) BETWEEN 1 AND 16) "
            "AND (delegated_by_actor_id IS NULL OR length(delegated_by_actor_id) BETWEEN 1 AND 128) "
            "AND (workflow_run_id IS NULL OR length(workflow_run_id) BETWEEN 1 AND 128) "
            "AND (agent_id IS NULL OR length(agent_id) BETWEEN 1 AND 128) "
            "AND (integration_id IS NULL OR length(integration_id) BETWEEN 1 AND 128) "
            "AND (target_id IS NULL OR length(target_id) BETWEEN 1 AND 128) "
            "AND (authority_role IS NULL OR length(authority_role) BETWEEN 1 AND 16)",
            name="bounds",
        ),
        CheckConstraint(
            "((delegated_by_type IS NULL AND delegated_by_actor_id IS NULL) "
            "OR (delegated_by_type IS NOT NULL AND delegated_by_actor_id IS NOT NULL)) "
            "AND (principal_type <> 'USER' OR (delegated_by_type IS NULL AND delegated_by_actor_id IS NULL "
            "AND workflow_run_id IS NULL AND agent_id IS NULL AND integration_id IS NULL)) "
            "AND (principal_type <> 'AGENT' OR (agent_id IS NOT NULL AND agent_id = actor_id)) "
            "AND (principal_type <> 'WORKFLOW' OR (workflow_run_id IS NOT NULL AND workflow_run_id = actor_id)) "
            "AND (principal_type <> 'INTEGRATION' OR (integration_id IS NOT NULL AND integration_id = actor_id))",
            name="delegator_pair",
        ),
        CheckConstraint(
            "((action IN ('lead.create','lead.lifecycle.change') AND target_type = 'lead') "
            "OR (action = 'lead.import' AND target_type = 'lead_import')) "
            "AND ((outcome = 'SUCCEEDED' AND target_id IS NOT NULL) "
            "OR (outcome = 'DENIED' AND target_id IS NULL))",
            name="target",
        ),
        Index("ix_audit_events_org_time", "organization_id", "occurred_at", "event_id"),
        Index("ix_audit_events_org_actor_time", "organization_id", "principal_type", "actor_id", "occurred_at", "event_id"),
        Index("ix_audit_events_org_correlation", "organization_id", "correlation_id", "occurred_at", "event_id"),
        Index("ix_audit_events_org_action_time", "organization_id", "action", "occurred_at", "event_id"),
        Index("ix_audit_events_org_target_time", "organization_id", "target_type", "target_id", "occurred_at", "event_id"),
    )


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def _reject_historical_mutation(_mapper, _connection, _target):
    """Only this mapper: raw/Core SQL and database owners remain outside the guard."""
    raise ValueError("Audit events are append-only through the ORM.")
