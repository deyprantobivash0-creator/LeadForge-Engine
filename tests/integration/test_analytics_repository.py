"""Direct SQL repository isolation checks on disposable tenant data."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from backend.database.session import SessionLocal, engine
from backend.models import LeadAnalysis
from backend.repositories.lead_analysis_repository import LeadAnalysisRepository


def test_scoped_counts_average_rows_and_priority(analytics_workspace):
    ids = analytics_workspace["ids"]["organizations"]
    repository = LeadAnalysisRepository()
    with SessionLocal() as db:
        assert repository.count(db, ids["a"]) == 4
        assert repository.count(db, ids["b"]) == 3
        assert repository.average_lead_score(db, ids["a"]) == 47.5
        assert repository.average_lead_score(db, ids["b"]) == 71.33
        assert repository.count_by_priority(db, ids["a"], "Hot") == 2
        assert repository.count_by_priority(db, ids["b"], "Hot") == 1
        assert {row.company for row in repository.get_all(db, ids["a"])} == {
            "Alpha Company", "Alpha Second", "Shared Alpha", "Alpha Cold",
        }
        assert repository.summary(db, ids["a"]) == {
            "total_leads": 4, "hot_leads": 2, "warm_leads": 1,
            "cold_leads": 1, "average_lead_score": 47.5,
        }


def test_tenant_predicate_precedes_order_and_limit(analytics_workspace):
    ids = analytics_workspace["ids"]["organizations"]
    repository = LeadAnalysisRepository()
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with SessionLocal() as db:
            top_a = repository.top_by_score(db, ids["a"], 2)
            assert [row.lead_score for row in top_a] == [80, 60]
            top_b = repository.top_by_score(db, ids["b"], 2)
            assert [row.lead_score for row in top_b] == [99, 95]
            assert [row.company for row in repository.top_by_score(db, ids["a"], 1, priority="Warm")] == ["Shared Alpha"]
            assert all(row.organization_id == ids["a"] for row in repository.recent(db, ids["a"], 3))
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert any("where lead_analysis.organization_id" in statement and "limit" in statement for statement in statements)


def test_date_window_is_half_open_and_tenant_scoped(analytics_workspace):
    ids = analytics_workspace["ids"]["organizations"]
    repository = LeadAnalysisRepository()
    start = datetime(2020, 1, 1)
    end = start + timedelta(days=1)
    with SessionLocal() as db:
        db.add_all([
            LeadAnalysis(organization_id=ids["a"], company="A boundary start", email="start@example.com", priority="Hot", lead_score=25, result={}, created_at=start),
            LeadAnalysis(organization_id=ids["a"], company="A boundary end", email="end@example.com", priority="Hot", lead_score=50, result={}, created_at=end),
            LeadAnalysis(organization_id=ids["b"], company="B same instant", email="b@example.com", priority="Hot", lead_score=99, result={}, created_at=start),
        ])
        db.commit()
        rows = repository.get_between_dates(db, ids["a"], start, end)
        assert [row.company for row in rows] == ["A boundary start"]
        assert repository.summary(db, ids["a"], start, end)["total_leads"] == 1
        assert [row.company for row in repository.top_by_score(db, ids["a"], 5, start_date=start, end_date=end)] == ["A boundary start"]
        with pytest.raises(ValueError):
            repository.get_between_dates(db, ids["a"], end, start)
        with pytest.raises(ValueError):
            repository.summary(db, ids["a"], start, start)


def test_empty_organization_returns_zeroes(analytics_workspace):
    empty_id = analytics_workspace["ids"]["organizations"]["empty"]
    repository = LeadAnalysisRepository()
    with SessionLocal() as db:
        assert repository.get_all(db, empty_id) == []
        assert repository.count(db, empty_id) == 0
        assert repository.count_by_priority(db, empty_id, "Hot") == 0
        assert repository.average_lead_score(db, empty_id) == 0
        assert repository.summary(db, empty_id)["total_leads"] == 0
        assert repository.top_by_score(db, empty_id, 5) == []
