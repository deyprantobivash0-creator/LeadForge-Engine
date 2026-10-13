"""add audit ledger persistence

Revision ID: 5d59e6268f43
Revises: e5d4c3b2a1f0
Create Date: 2026-10-13 14:26:22.521933

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d59e6268f43'
down_revision: Union[str, Sequence[str], None] = 'e5d4c3b2a1f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add audit persistence only; no existing table or historical-data changes."""
    op.create_table(
        "audit_events",
        sa.Column('event_id', sa.String(36), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('outcome', sa.String(16), nullable=False),
        sa.Column('reason_code', sa.String(48), nullable=False),
        sa.Column('principal_type', sa.String(16), nullable=False),
        sa.Column('actor_id', sa.String(128), nullable=False),
        sa.Column('delegated_by_type', sa.String(16), nullable=True),
        sa.Column('delegated_by_actor_id', sa.String(128), nullable=True),
        sa.Column('correlation_id', sa.String(64), nullable=False),
        sa.Column('workflow_run_id', sa.String(128), nullable=True),
        sa.Column('agent_id', sa.String(128), nullable=True),
        sa.Column('integration_id', sa.String(128), nullable=True),
        sa.Column('target_type', sa.String(32), nullable=False),
        sa.Column('target_id', sa.String(128), nullable=True),
        sa.Column('authorization_evidence', sa.JSON(none_as_null=True), nullable=False),
        sa.Column('authority_role', sa.String(16), nullable=True),
        sa.Column('details', sa.JSON(none_as_null=True), nullable=False),
        sa.Column('schema_version', sa.SmallInteger(), nullable=False),
        sa.CheckConstraint('length(event_id) = 36 AND length(event_type) BETWEEN 1 AND 64 AND length(action) BETWEEN 1 AND 64 AND length(outcome) BETWEEN 1 AND 16 AND length(reason_code) BETWEEN 1 AND 48 AND length(principal_type) BETWEEN 1 AND 16 AND length(actor_id) BETWEEN 1 AND 128 AND length(correlation_id) BETWEEN 1 AND 64 AND length(target_type) BETWEEN 1 AND 32 AND schema_version = 1 AND (delegated_by_type IS NULL OR length(delegated_by_type) BETWEEN 1 AND 16) AND (delegated_by_actor_id IS NULL OR length(delegated_by_actor_id) BETWEEN 1 AND 128) AND (workflow_run_id IS NULL OR length(workflow_run_id) BETWEEN 1 AND 128) AND (agent_id IS NULL OR length(agent_id) BETWEEN 1 AND 128) AND (integration_id IS NULL OR length(integration_id) BETWEEN 1 AND 128) AND (target_id IS NULL OR length(target_id) BETWEEN 1 AND 128) AND (authority_role IS NULL OR length(authority_role) BETWEEN 1 AND 16)', name=op.f('ck_audit_events_bounds')),
        sa.CheckConstraint("((delegated_by_type IS NULL AND delegated_by_actor_id IS NULL) OR (delegated_by_type IS NOT NULL AND delegated_by_actor_id IS NOT NULL)) AND (principal_type <> 'USER' OR (delegated_by_type IS NULL AND delegated_by_actor_id IS NULL AND workflow_run_id IS NULL AND agent_id IS NULL AND integration_id IS NULL)) AND (principal_type <> 'AGENT' OR (agent_id IS NOT NULL AND agent_id = actor_id)) AND (principal_type <> 'WORKFLOW' OR (workflow_run_id IS NOT NULL AND workflow_run_id = actor_id)) AND (principal_type <> 'INTEGRATION' OR (integration_id IS NOT NULL AND integration_id = actor_id))", name=op.f('ck_audit_events_delegator_pair')),
        sa.CheckConstraint("event_type IN ('business.command.completed','permission.denied','security.command.rejected') AND action IN ('lead.create','lead.lifecycle.change','lead.import') AND outcome IN ('SUCCEEDED','DENIED') AND reason_code IN ('COMMAND_COMPLETED','ACTION_PERMISSION_DENIED','EXECUTION_TENANT_MISMATCH') AND principal_type IN ('USER','SYSTEM','AGENT','WORKFLOW','INTEGRATION') AND (delegated_by_type IS NULL OR delegated_by_type IN ('USER','SYSTEM','AGENT','WORKFLOW','INTEGRATION')) AND target_type IN ('lead','lead_import') AND (authority_role IS NULL OR authority_role IN ('owner','admin','member'))", name=op.f('ck_audit_events_domains')),
        sa.CheckConstraint("(event_type = 'business.command.completed' AND outcome = 'SUCCEEDED' AND reason_code = 'COMMAND_COMPLETED') OR (event_type = 'permission.denied' AND outcome = 'DENIED' AND reason_code = 'ACTION_PERMISSION_DENIED') OR (event_type = 'security.command.rejected' AND outcome = 'DENIED' AND reason_code = 'EXECUTION_TENANT_MISMATCH')", name=op.f('ck_audit_events_event_outcome')),
        sa.CheckConstraint("((action IN ('lead.create','lead.lifecycle.change') AND target_type = 'lead') OR (action = 'lead.import' AND target_type = 'lead_import')) AND ((outcome = 'SUCCEEDED' AND target_id IS NOT NULL) OR (outcome = 'DENIED' AND target_id IS NULL))", name=op.f('ck_audit_events_target')),
        sa.CheckConstraint('organization_id > 0', name=op.f('ck_audit_events_tenant_positive')),
        sa.PrimaryKeyConstraint('event_id', name=op.f('pk_audit_events')),
    )
    op.create_index('ix_audit_events_org_action_time', "audit_events", ['organization_id', 'action', 'occurred_at', 'event_id'], unique=False)
    op.create_index('ix_audit_events_org_actor_time', "audit_events", ['organization_id', 'principal_type', 'actor_id', 'occurred_at', 'event_id'], unique=False)
    op.create_index('ix_audit_events_org_correlation', "audit_events", ['organization_id', 'correlation_id', 'occurred_at', 'event_id'], unique=False)
    op.create_index('ix_audit_events_org_target_time', "audit_events", ['organization_id', 'target_type', 'target_id', 'occurred_at', 'event_id'], unique=False)
    op.create_index('ix_audit_events_org_time', "audit_events", ['organization_id', 'occurred_at', 'event_id'], unique=False)


def downgrade() -> None:
    """Destroys audit evidence; validate only in disposable databases."""
    op.drop_index('ix_audit_events_org_time', table_name="audit_events")
    op.drop_index('ix_audit_events_org_target_time', table_name="audit_events")
    op.drop_index('ix_audit_events_org_correlation', table_name="audit_events")
    op.drop_index('ix_audit_events_org_actor_time', table_name="audit_events")
    op.drop_index('ix_audit_events_org_action_time', table_name="audit_events")
    op.drop_table("audit_events")
