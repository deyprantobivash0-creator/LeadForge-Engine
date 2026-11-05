from datetime import datetime, timedelta

from sqlalchemy import and_, select, update
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from backend.models.lead import Lead
from backend.repositories.lead_analysis_repository import LeadAnalysisRepository


class LeadRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_lead(self, lead: Lead) -> Lead:
        self.db.add(lead)
        self.db.flush()
        return lead

    def get_all_leads(
        self,
        organization_id: int,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
        priority: str | None = None,
        processing_status: str | None = None,
        source: str | None = None,
        analysis_state: str | None = None,
    ):
        return self._list_leads(
            organization_id, page, page_size,
            status=status, priority=priority,
            processing_status=processing_status, source=source,
            analysis_state=analysis_state,
        )

    def get_lead_by_id(
        self,
        lead_id: int,
        organization_id: int,
    ) -> Lead | None:
        return (
            self.db.query(Lead)
            .filter(
                Lead.id == lead_id,
                Lead.organization_id == organization_id,
            )
            .first()
        )

    def get_lead_for_lifecycle_update(
        self, lead_id: int, organization_id: int,
    ) -> Lead | None:
        """Acquire refreshed tenant-owned state under the caller's E02 root.

        E02 alone validates transaction ownership and physical provenance.
        Acquire before scalar snapshots or pending ORM changes: refreshing must
        neither overwrite pending values nor implicitly flush unrelated work.
        PostgreSQL locks the matching row until root settlement. SQLite's scoped
        primary-key self-update reserves its database-wide writer before SELECT;
        it is not a row lock. The managed Lead schema has no UPDATE triggers or
        on-update columns. Busy/snapshot errors propagate to the E02 caller.
        Savepoint acquisition is excluded because its lock could be released
        before the root settles; logical nested E02 scopes share the root.
        """
        # Keep configuration-dependent imports behind the disposable PG fixture.
        from backend.database.transaction_policy import require_governed_physical_root

        require_governed_physical_root(self.db)
        # populate_existing must never discard pending values or cause an
        # implicit autoflush before ownership is established.
        if self.db.new or self.db.dirty or self.db.deleted:
            raise InvalidRequestError("Flush pending ORM changes before lifecycle acquisition.")
        if self.db.in_nested_transaction():
            raise InvalidRequestError("Lifecycle acquisition requires the owning transaction, not a savepoint.")
        dialect = self.db.get_bind().dialect.name
        if dialect not in {"postgresql", "sqlite"}:
            raise InvalidRequestError("Unsupported database for lifecycle acquisition.")
        with self.db.no_autoflush:
            predicate = (Lead.organization_id == organization_id, Lead.id == lead_id)
            if dialect == "sqlite":
                self.db.execute(update(Lead).where(*predicate).values(id=Lead.id)
                                .execution_options(synchronize_session=False))
            query = select(Lead).where(*predicate).execution_options(populate_existing=True)
            if dialect == "postgresql":
                query = query.with_for_update(of=Lead)
            return self.db.execute(query).scalar_one_or_none()

    def get_lead_by_email(
        self,
        email: str,
        organization_id: int,
    ) -> Lead | None:
        return (
            self.db.query(Lead)
            .filter(
                Lead.email == email,
                Lead.organization_id == organization_id,
            )
            .first()
        )

    def search_leads(
        self,
        organization_id: int,
        company: str | None = None,
        email: str | None = None,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
        priority: str | None = None,
        processing_status: str | None = None,
        source: str | None = None,
        analysis_state: str | None = None,
    ):
        return self._list_leads(
            organization_id, page, page_size,
            company=company, email=email, status=status,
            priority=priority, processing_status=processing_status,
            source=source, analysis_state=analysis_state,
        )

    def _list_leads(
        self,
        organization_id: int,
        page: int,
        page_size: int,
        *,
        company: str | None = None,
        email: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        processing_status: str | None = None,
        source: str | None = None,
        analysis_state: str | None = None,
    ):
        latest = LeadAnalysisRepository.current_ranked_subquery(organization_id)
        query = (
            self.db.query(
                Lead, latest.c.analysis_id,
                latest.c.analysis_score, latest.c.analysis_priority,
            )
            .outerjoin(latest, and_(
                Lead.organization_id == latest.c.organization_id,
                Lead.id == latest.c.lead_id,
                latest.c.rank == 1,
            ))
            .filter(Lead.organization_id == organization_id)
        )
        if company:
            query = query.filter(Lead.company.ilike(f"%{company}%"))
        if email:
            query = query.filter(Lead.email.ilike(f"%{email}%"))
        if status:
            query = query.filter(Lead.status == status)
        if priority:
            query = query.filter(latest.c.analysis_priority == priority)
        if processing_status:
            query = query.filter(Lead.processing_status == processing_status)
        if source:
            query = query.filter(Lead.source.ilike(f"%{source}%"))
        if analysis_state == "analyzed":
            query = query.filter(latest.c.analysis_id.is_not(None))
        elif analysis_state == "unanalyzed":
            query = query.filter(latest.c.analysis_id.is_(None))

        total = query.count()
        items = query.order_by(Lead.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    def update_status(
        self,
        lead_id: int,
        organization_id: int,
        status: str,
    ) -> Lead | None:
        lead = self.get_lead_by_id(
            lead_id=lead_id,
            organization_id=organization_id,
        )

        if not lead:
            return None

        lead.status = status

        self.db.flush()

        return lead

    def update_lifecycle(
        self,
        lead_id: int,
        organization_id: int,
        status: str | None = None,
        notes: str | None = None,
        last_contacted: datetime | None = None,
        next_follow_up: datetime | None = None,
    ) -> Lead | None:

        lead = self.get_lead_by_id(
            lead_id=lead_id,
            organization_id=organization_id,
        )

        if not lead:
            return None

        if status is not None:
            lead.status = status

        if notes is not None:
            lead.notes = notes

        if last_contacted is not None:
            lead.last_contacted = last_contacted

        if next_follow_up is not None:
            lead.next_follow_up = next_follow_up

        self.db.flush()

        return lead

    def get_follow_up_leads(
        self,
        organization_id: int,
        days: int = 7,
        page: int = 1,
        page_size: int = 50,
    ):
        now = datetime.utcnow()
        end_date = now + timedelta(days=days)

        query = (
            self.db.query(Lead)
            .filter(
                Lead.organization_id == organization_id,
                Lead.next_follow_up.is_not(None),
                Lead.next_follow_up >= now,
                Lead.next_follow_up <= end_date,
            )
        )

        total = query.count()

        offset = (page - 1) * page_size

        items = (
            query
            .order_by(Lead.next_follow_up.asc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return items, total
