"""sync processing status

Revision ID: 24b5b28b09b7
Revises: e37cdcdf31dd
Create Date: 2026-09-24 01:18:19.549254

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '24b5b28b09b7'
down_revision: Union[str, Sequence[str], None] = 'e37cdcdf31dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = {c["name"] for c in inspector.get_columns("leads")}

    if "processing_status" not in columns:
        op.add_column(
            "leads",
            sa.Column(
                "processing_status",
                sa.String(length=50),
                nullable=False,
                server_default="pending",
            ),
        )

    inspector = inspect(bind)
    indexes = {i["name"] for i in inspector.get_indexes("leads")}

    if "ix_leads_processing_status" not in indexes:
        op.create_index(
            "ix_leads_processing_status",
            "leads",
            ["processing_status"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    indexes = {i["name"] for i in inspector.get_indexes("leads")}

    if "ix_leads_processing_status" in indexes:
        op.drop_index(
            "ix_leads_processing_status",
            table_name="leads",
        )

    columns = {c["name"] for c in inspector.get_columns("leads")}

    if "processing_status" in columns:
        op.drop_column("leads", "processing_status")