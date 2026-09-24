"""add ingestion jobs

Revision ID: e37cdcdf31dd
Revises: 9ed1e76d4c54
Create Date: 2026-08-30

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "e37cdcdf31dd"
down_revision: Union[str, Sequence[str], None] = "9ed1e76d4c54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # ---------------------------------------------------------
    # 1. Ensure ingestion_jobs table exists
    # ---------------------------------------------------------

    existing_tables = set(inspector.get_table_names())

    if "ingestion_jobs" not in existing_tables:
        op.create_table(
            "ingestion_jobs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "filename",
                sa.String(length=255),
                nullable=False,
            ),
            sa.Column(
                "source_type",
                sa.String(length=50),
                nullable=False,
            ),
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default="pending",
            ),
            sa.Column(
                "total_rows",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "processed_rows",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "successful_rows",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "failed_rows",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "error_message",
                sa.Text(),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "started_at",
                sa.DateTime(),
                nullable=True,
            ),
            sa.Column(
                "completed_at",
                sa.DateTime(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organizations.id"],
                name="fk_ingestion_jobs_organization_id",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    # Re-inspect after possible table creation.
    inspector = inspect(bind)

    # ---------------------------------------------------------
    # 2. Ensure ingestion_jobs indexes exist
    # ---------------------------------------------------------

    existing_indexes = {
        index["name"]
        for index in inspector.get_indexes("ingestion_jobs")
    }

    if "ix_ingestion_jobs_id" not in existing_indexes:
        op.create_index(
            "ix_ingestion_jobs_id",
            "ingestion_jobs",
            ["id"],
            unique=False,
        )

    if "ix_ingestion_jobs_organization_id" not in existing_indexes:
        op.create_index(
            "ix_ingestion_jobs_organization_id",
            "ingestion_jobs",
            ["organization_id"],
            unique=False,
        )

    if "ix_ingestion_jobs_status" not in existing_indexes:
        op.create_index(
            "ix_ingestion_jobs_status",
            "ingestion_jobs",
            ["status"],
            unique=False,
        )

    # ---------------------------------------------------------
    # 3. Repair the pre-existing lead_analysis id index
    # ---------------------------------------------------------
    #
    # Older schema already contains ix_lead_analysis_id.
    # Therefore we MUST NOT create it again.
    #

    inspector = inspect(bind)

    if "lead_analysis" in inspector.get_table_names():
        existing_indexes = {
            index["name"]
            for index in inspector.get_indexes("lead_analysis")
        }

        if "ix_lead_analysis_id" not in existing_indexes:
            op.create_index(
                "ix_lead_analysis_id",
                "lead_analysis",
                ["id"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # ---------------------------------------------------------
    # Remove ingestion_jobs indexes
    # ---------------------------------------------------------

    if "ingestion_jobs" in inspector.get_table_names():
        existing_indexes = {
            index["name"]
            for index in inspector.get_indexes("ingestion_jobs")
        }

        if "ix_ingestion_jobs_status" in existing_indexes:
            op.drop_index(
                "ix_ingestion_jobs_status",
                table_name="ingestion_jobs",
            )

        if "ix_ingestion_jobs_organization_id" in existing_indexes:
            op.drop_index(
                "ix_ingestion_jobs_organization_id",
                table_name="ingestion_jobs",
            )

        if "ix_ingestion_jobs_id" in existing_indexes:
            op.drop_index(
                "ix_ingestion_jobs_id",
                table_name="ingestion_jobs",
            )

        op.drop_table("ingestion_jobs")

    # ---------------------------------------------------------
    # Do NOT remove ix_lead_analysis_id during downgrade.
    #
    # It may have existed before this migration.
    # ---------------------------------------------------------