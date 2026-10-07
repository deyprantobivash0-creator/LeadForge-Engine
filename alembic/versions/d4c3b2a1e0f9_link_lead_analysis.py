"""Link analysis history to tenant-owned leads.

Revision ID: d4c3b2a1e0f9
Revises: c3b2a1d0e9f8
"""

from alembic import op
import sqlalchemy as sa


revision = "d4c3b2a1e0f9"
down_revision = "c3b2a1d0e9f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # The existing email key is unique today, but count explicitly so this
    # backfill remains safe if an older installation has ambiguous rows.
    with op.batch_alter_table("leads") as batch:
        batch.create_unique_constraint("uq_leads_organization_id_id", ["organization_id", "id"])
    with op.batch_alter_table("lead_analysis") as batch:
        batch.add_column(sa.Column("lead_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_lead_analysis_organization_lead", "leads",
            ["organization_id", "lead_id"], ["organization_id", "id"],
            ondelete="RESTRICT",
        )
    bind.execute(sa.text("""
        UPDATE lead_analysis SET lead_id = (
            SELECT MIN(leads.id) FROM leads
            WHERE leads.organization_id = lead_analysis.organization_id
              AND leads.email = lead_analysis.email
            HAVING COUNT(*) = 1
        )
    """))
    op.create_index(
        "ix_lead_analysis_org_lead_created", "lead_analysis",
        ["organization_id", "lead_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lead_analysis_org_lead_created", table_name="lead_analysis")
    with op.batch_alter_table("lead_analysis") as batch:
        batch.drop_constraint("fk_lead_analysis_organization_lead", type_="foreignkey")
        batch.drop_column("lead_id")
    with op.batch_alter_table("leads") as batch:
        batch.drop_constraint("uq_leads_organization_id_id", type_="unique")
