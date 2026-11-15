"""Add later outcome evidence without modifying recorded decisions or backfilling.

Revision ID: 72b6a8d9e014
Revises: 31e5e19bd71f
"""
from alembic import op
import sqlalchemy as sa

revision = "72b6a8d9e014"
down_revision = "31e5e19bd71f"
branch_labels = None
depends_on = None


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Outcome history supports SQLite and PostgreSQL only.")
    op.create_index("ux_decision_ledger_scope_id", "decision_ledger", ["organization_id", "lead_id", "id"], unique=True)
    op.create_table("decision_outcomes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("decision_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["organization_id", "lead_id", "decision_id"],
            ["decision_ledger.organization_id", "decision_ledger.lead_id", "decision_ledger.id"],
            ondelete="RESTRICT", name="fk_outcome_scoped_decision"),
        sa.CheckConstraint("kind IN ('Contacted','Qualified','Meeting','Won','Lost')", name=op.f("ck_decision_outcomes_outcome_kind")),
        sa.CheckConstraint("organization_id > 0 AND lead_id > 0 AND recorded_by_user_id > 0 AND length(id) = 36", name=op.f("ck_decision_outcomes_outcome_identity")),
        sa.CheckConstraint("note IS NULL OR length(note) <= 1000", name=op.f("ck_decision_outcomes_outcome_note")),
        sa.CheckConstraint("observed_at <= recorded_at", name=op.f("ck_decision_outcomes_outcome_time")),
    )
    op.create_index("ix_outcomes_decision_time", "decision_outcomes", ["organization_id", "lead_id", "decision_id", "observed_at", "recorded_at", "id"])
    if dialect == "postgresql":
        op.execute("""CREATE FUNCTION lf_outcomes_immutable_v1() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Outcome evidence is immutable.' USING ERRCODE = '23514'; RETURN OLD; END; $$""")
        op.execute("CREATE TRIGGER outcomes_immutable BEFORE UPDATE OR DELETE ON decision_outcomes FOR EACH ROW EXECUTE FUNCTION lf_outcomes_immutable_v1()")
    else:
        for action in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER outcomes_no_{action.lower()} BEFORE {action} ON decision_outcomes BEGIN SELECT RAISE(ABORT, 'Outcome evidence is immutable.'); END")


def downgrade():
    """Destructive rollback of new outcome evidence; never run on the working DB."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER outcomes_immutable ON decision_outcomes")
        op.execute("DROP FUNCTION lf_outcomes_immutable_v1()")
    else:
        op.execute("DROP TRIGGER outcomes_no_update")
        op.execute("DROP TRIGGER outcomes_no_delete")
    op.drop_index("ix_outcomes_decision_time", table_name="decision_outcomes")
    op.drop_table("decision_outcomes")
    op.drop_index("ux_decision_ledger_scope_id", table_name="decision_ledger")
