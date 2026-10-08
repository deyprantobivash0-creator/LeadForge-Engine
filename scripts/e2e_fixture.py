"""Stdin helper: seed/fault/query only the explicitly disposable Step 5J database."""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from backend.core.config import settings, secret_value
from backend.core.passwords import hash_password
from backend.database.session import SessionLocal
from backend.models import Lead, LeadAnalysis, Organization, OrganizationMembership, User

assert os.environ.get('LEADFORGE_E2E_DISPOSABLE') == 'true'
assert settings.ENVIRONMENT == 'development' and settings.AI_PROVIDER == 'mock'
assert make_url(secret_value(settings.DATABASE_URL)).database == 'leadforge_dev'
mode = sys.argv[1]
with SessionLocal() as db:
    if mode == 'seed':
        assert db.scalar(select(User.id).limit(1)) is None, 'Must be fresh disposable database'
        user = User(email='e2e@example.com', password_hash=hash_password('local synthetic E2E password'))
        orgs = [Organization(name='E2E ' + name, slug='e2e-' + name.lower()) for name in ['Alpha', 'Beta', 'Empty']]
        db.add_all([user, *orgs, User(email='no-workspace@example.com', password_hash=hash_password('local synthetic E2E password'))]); db.flush()
        db.add_all([OrganizationMembership(user_id=user.id, organization_id=o.id, role='owner') for o in orgs])
        for index, org in enumerate(orgs[:2]):
            db.add(Lead(organization_id=org.id, company='E2E Synthetic Lead' if index == 0 else 'Tenant Beta Sentinel', email=f'fixture-{index}@example.com', source='e2e'))
        db.commit()
        lead = db.scalar(select(Lead).where(Lead.organization_id == orgs[0].id))
        for score in [80, 30]:
            db.add(LeadAnalysis(organization_id=orgs[0].id, lead_id=lead.id, company=lead.company, email=lead.email, priority='Hot' if score == 80 else 'Cold', lead_score=score, result={}, created_at=datetime.utcnow()))
        lead.processing_status = 'completed'; lead.lead_score = 30; lead.priority = 'Cold'
        populated = Organization(name='E2E Populated', slug='e2e-populated')
        db.add(populated); db.flush()
        db.add(OrganizationMembership(user_id=user.id, organization_id=populated.id, role='owner'))
        for index, state in enumerate(['New', 'Qualified', 'Contacted', 'Meeting', 'Won', 'Lost']):
            item = Lead(organization_id=populated.id, company='Populated ' + state, email=f'populated-{index}@example.com', source='synthetic-release', status=state)
            db.add(item); db.flush()
            if index < 3:
                score, priority = [(90, 'Hot'), (65, 'Warm'), (30, 'Cold')][index]
                db.add(LeadAnalysis(organization_id=populated.id, lead_id=item.id, company=item.company, email=item.email, priority=priority, lead_score=score, result={}))
                item.lead_score = score; item.priority = priority; item.processing_status = 'completed'
        db.commit()
        print(json.dumps({'synthetic': True, 'organizations': [o.id for o in orgs], 'lead_id': lead.id}))
    elif mode == 'failed-analysis':
        from backend.ai.providers.base import ProviderUnavailable
        from backend.services.lead_processing_service import LeadProcessingService, ProcessingFailure
        class FailedMock:
            async def generate_structured(self, *args, **kwargs):
                raise ProviderUnavailable('synthetic local fault')
        lead = db.scalar(select(Lead).where(Lead.email == 'fixture-0@example.com'))
        previous_score_priority = (lead.lead_score, lead.priority)
        before = db.scalar(select(LeadAnalysis.id).where(LeadAnalysis.lead_id == lead.id).order_by(LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc()).limit(1))
        try:
            asyncio.run(LeadProcessingService(db, provider=FailedMock()).process(lead.organization_id, lead.id))
        except ProcessingFailure:
            pass
        else:
            raise AssertionError('Fault must fail')
        db.refresh(lead)
        after = db.scalar(select(LeadAnalysis.id).where(LeadAnalysis.lead_id == lead.id).order_by(LeadAnalysis.created_at.desc(), LeadAnalysis.id.desc()).limit(1))
        assert before == after and lead.processing_status == 'failed'
        assert (lead.lead_score, lead.priority) == previous_score_priority
        print(json.dumps({'failed_later_analysis_preserves_current': True, 'analysis_id': after}))
    elif mode == 'connections':
        print(json.dumps([dict(row._mapping) for row in db.execute(text("SELECT state, count(*) AS count FROM pg_stat_activity WHERE datname=current_database() GROUP BY state"))]))
    elif mode == 'query-review':
        from time import perf_counter
        from sqlalchemy import event
        from backend.database.session import engine
        from backend.dashboard.dashboard_service import DashboardService
        from backend.services.report_v2_service import ReportV2Service
        from backend.services.lead_service import LeadService
        org = db.scalar(select(Organization.id).where(Organization.slug == 'e2e-alpha'))
        statements = []
        @event.listens_for(engine, 'before_cursor_execute')
        def before_query(connection, cursor, statement, parameters, context, executemany):
            context.e2e_started = perf_counter()
        @event.listens_for(engine, 'after_cursor_execute')
        def after_query(connection, cursor, statement, parameters, context, executemany):
            statements.append({'sql': statement, 'duration_ms': (perf_counter() - context.e2e_started) * 1000})
        results = {}
        for name, operation in [('leads-20', lambda: LeadService(db).get_leads(org, page_size=20)), ('leads-100', lambda: LeadService(db).get_leads(org, page_size=100)), ('dashboard', lambda: DashboardService(db).current_overview(org)), ('reports', lambda: ReportV2Service(db).overview(org, 'today'))]:
            statements.clear(); operation()
            results[name] = {'query_count': len(statements), 'max_query_ms': round(max(s['duration_ms'] for s in statements), 2), 'sql': [s['sql'] for s in statements]}
        assert results['leads-20']['query_count'] == results['leads-100']['query_count'] == 2
        print(json.dumps(results))
    elif mode == 'expire':
        from backend.models.auth_session import AuthSession
        for session in db.scalars(select(AuthSession)):
            session.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit(); print('Expired only disposable synthetic sessions')
    else:
        raise ValueError('Unknown fixture action')
