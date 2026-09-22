"""canonicalize multitenant schema

Revision ID: 9ed1e76d4c54
Revises:
Create Date: 2026-09-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9ed1e76d4c54"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_full_schema() -> None:
    """Create the complete canonical schema for a fresh database."""

    op.create_table(
        "organizations",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "slug",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "plan",
            sa.String(length=50),
            nullable=False,
            server_default="standard",
        ),
        sa.Column(
            "monthly_lead_limit",
            sa.Integer(),
            nullable=False,
            server_default="500",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "slug",
            name="uq_organizations_slug",
        ),
    )

    op.create_index(
        "ix_organizations_id",
        "organizations",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_organizations_slug",
        "organizations",
        ["slug"],
        unique=True,
    )

    op.create_table(
        "leads",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "company",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "industry",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "lead_score",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "priority",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "ai_reason",
            sa.String(length=1000),
            nullable=True,
        ),
        sa.Column(
            "next_action",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="New",
        ),
        sa.Column(
            "notes",
            sa.String(length=2000),
            nullable=True,
        ),
        sa.Column(
            "last_contacted",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "next_follow_up",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_leads_organization_id_organizations",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "email",
            name="uq_leads_organization_email",
        ),
    )

    op.create_index(
        "ix_leads_id",
        "leads",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_leads_organization_id",
        "leads",
        ["organization_id"],
        unique=False,
    )

    op.create_index(
        "ix_leads_status",
        "leads",
        ["status"],
        unique=False,
    )

    op.create_index(
        "ix_leads_next_follow_up",
        "leads",
        ["next_follow_up"],
        unique=False,
    )

    op.create_index(
        "ix_leads_created_at",
        "leads",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_leads_org_created",
        "leads",
        ["organization_id", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_leads_org_status",
        "leads",
        ["organization_id", "status"],
        unique=False,
    )

    op.create_index(
        "ix_leads_org_followup",
        "leads",
        ["organization_id", "next_follow_up"],
        unique=False,
    )

    op.create_table(
        "lead_analysis",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "company",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "lead_score",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "result",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_lead_analysis_organization_id_organizations",
        ),
    )

    op.create_index(
        "ix_lead_analysis_id",
        "lead_analysis",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_lead_analysis_organization_id",
        "lead_analysis",
        ["organization_id"],
        unique=False,
    )


def _upgrade_existing_sqlite() -> None:
    """
    Rebuild the existing SQLite tables into the canonical schema.

    SQLite has limited ALTER TABLE support, so table recreation is
    safer than attempting direct ALTER COLUMN / DROP CONSTRAINT
    operations.
    """

    connection = op.get_bind()

    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")

    metadata = sa.MetaData()

    organizations = sa.Table(
        "organizations",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False),
        sa.Column("monthly_lead_limit", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "slug",
            name="uq_organizations_slug",
        ),
    )

    leads = sa.Table(
        "leads",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("industry", sa.String(100)),
        sa.Column("lead_score", sa.Integer()),
        sa.Column("priority", sa.String(50)),
        sa.Column("ai_reason", sa.String(1000)),
        sa.Column("next_action", sa.String(500)),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
        ),
        sa.Column("notes", sa.String(2000)),
        sa.Column("last_contacted", sa.DateTime()),
        sa.Column("next_follow_up", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_leads_organization_id_organizations",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "email",
            name="uq_leads_organization_email",
        ),
    )

    lead_analysis = sa.Table(
        "lead_analysis",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("priority", sa.String(50), nullable=False),
        sa.Column("lead_score", sa.Integer(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_lead_analysis_organization_id_organizations",
        ),
    )

    existing_tables = set(
        sa.inspect(connection).get_table_names()
    )

    # Existing organizations table
    if "organizations" in existing_tables:
        with op.batch_alter_table(
            "organizations",
            recreate="always",
            copy_from=organizations,
        ):
            pass

    # Existing leads table
    if "leads" in existing_tables:
        with op.batch_alter_table(
            "leads",
            recreate="always",
            copy_from=leads,
        ):
            pass

    # Existing lead_analysis table
    if "lead_analysis" in existing_tables:
        with op.batch_alter_table(
            "lead_analysis",
            recreate="always",
            copy_from=lead_analysis,
        ):
            pass

    connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade() -> None:
    """Apply canonical LeadForge schema."""

    connection = op.get_bind()
    inspector = sa.inspect(connection)

    existing_tables = set(
        inspector.get_table_names()
    )

    required_tables = {
        "organizations",
        "leads",
        "lead_analysis",
    }

    if not required_tables.issubset(existing_tables):
        _create_full_schema()
    else:
        if connection.dialect.name == "sqlite":
            _upgrade_existing_sqlite()
        else:
            # Production databases created from scratch will use
            # the canonical schema directly.
            #
            # If an existing non-SQLite database reaches this branch,
            # fail explicitly instead of silently modifying production.
            raise RuntimeError(
                "Existing non-SQLite database detected. "
                "Create a dedicated production upgrade migration "
                "before applying this revision."
            )


def downgrade() -> None:
    """Remove the canonical LeadForge schema."""

    connection = op.get_bind()

    existing_tables = set(
        sa.inspect(connection).get_table_names()
    )

    if "lead_analysis" in existing_tables:
        op.drop_table("lead_analysis")

    if "leads" in existing_tables:
        op.drop_table("leads")

    if "organizations" in existing_tables:
        op.drop_table("organizations")