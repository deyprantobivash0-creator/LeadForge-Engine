"""Add immutable Revenue Brain decision history; no backfill.

Revision ID: 31e5e19bd71f
Revises: 5d59e6268f43
"""

from alembic import op
import sqlalchemy as sa


revision = "31e5e19bd71f"
down_revision = "5d59e6268f43"
branch_labels = None
depends_on = None


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Decision Ledger supports PostgreSQL and SQLite only.")
    op.create_table(
        "decision_ledger",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("decision_version", sa.String(64), nullable=False),
        sa.Column("opportunity_score", sa.Integer(), nullable=False),
        sa.Column("fit_score", sa.Integer(), nullable=False),
        sa.Column("readiness_score", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("recommended_action", sa.String(32), nullable=False),
        sa.Column("human_review_required", sa.Boolean(), nullable=False),
        sa.Column("reasons", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("evidence", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("risk_flags", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("missing_signals", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("decision_generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_ledger")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT",
                                name=op.f("fk_decision_ledger_organization_id_organizations")),
        sa.ForeignKeyConstraint(["organization_id", "lead_id"], ["leads.organization_id", "leads.id"],
                                ondelete="RESTRICT", name="fk_decision_ledger_organization_lead"),
        sa.CheckConstraint("organization_id > 0 AND lead_id > 0", name=op.f("ck_decision_ledger_positive_ownership")),
        sa.CheckConstraint("length(id) = 36 AND length(decision_version) BETWEEN 1 AND 64",
                           name=op.f("ck_decision_ledger_identity_bounds")),
        sa.CheckConstraint("opportunity_score BETWEEN 0 AND 100 AND fit_score BETWEEN 0 AND 100 "
                           "AND readiness_score BETWEEN 0 AND 100 AND confidence >= 0 AND confidence <= 1",
                           name=op.f("ck_decision_ledger_score_bounds")),
        sa.CheckConstraint("recommended_action IN ('RESEARCH_MORE','HUMAN_REVIEW','QUALIFY','PREPARE_OUTREACH','NURTURE','DEPRIORITIZE') "
                           "AND human_review_required IN (TRUE,FALSE)", name=op.f("ck_decision_ledger_decision_domains")),
        sa.CheckConstraint("length(CAST(reasons AS TEXT)) <= 65536 AND length(CAST(evidence AS TEXT)) <= 131072 "
                           "AND length(CAST(risk_flags AS TEXT)) <= 1024 AND length(CAST(missing_signals AS TEXT)) <= 1024",
                           name=op.f("ck_decision_ledger_json_bounds")),
    )
    op.create_index("ix_decision_ledger_org_lead_time", "decision_ledger",
                    ["organization_id", "lead_id", "recorded_at", "id"])
    if dialect == "postgresql":
        op.execute("""CREATE FUNCTION lf_decision_ledger_immutable_v1() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'Decision Ledger records are immutable.' USING ERRCODE = '23514';
            RETURN OLD; END; $$""")
        op.execute("""CREATE TRIGGER decision_ledger_immutable BEFORE UPDATE OR DELETE
            ON decision_ledger FOR EACH ROW EXECUTE FUNCTION lf_decision_ledger_immutable_v1()""")
    else:
        op.execute("""CREATE TRIGGER decision_ledger_no_update BEFORE UPDATE ON decision_ledger
            BEGIN SELECT RAISE(ABORT, 'Decision Ledger records are immutable.'); END""")
        op.execute("""CREATE TRIGGER decision_ledger_no_delete BEFORE DELETE ON decision_ledger
            BEGIN SELECT RAISE(ABORT, 'Decision Ledger records are immutable.'); END""")


def downgrade():
    """Explicitly destroys decision history; verify only on disposable databases."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER decision_ledger_immutable ON decision_ledger")
        op.execute("DROP FUNCTION lf_decision_ledger_immutable_v1()")
    else:
        op.execute("DROP TRIGGER decision_ledger_no_update")
        op.execute("DROP TRIGGER decision_ledger_no_delete")
    op.drop_index("ix_decision_ledger_org_lead_time", table_name="decision_ledger")
    op.drop_table("decision_ledger")
