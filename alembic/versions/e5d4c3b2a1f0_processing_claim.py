"""Add a recoverable processing lease.

Revision ID: e5d4c3b2a1f0
Revises: d4c3b2a1e0f9
"""

from alembic import op
import sqlalchemy as sa

revision = "e5d4c3b2a1f0"
down_revision = "d4c3b2a1e0f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("processing_started_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("processing_attempt_id", sa.String(36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.drop_column("processing_attempt_id")
        batch.drop_column("processing_started_at")
