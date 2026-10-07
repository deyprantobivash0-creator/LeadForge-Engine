from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from backend.database.base import Base

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index

class LeadAnalysis(Base):

    __tablename__ = "lead_analysis"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    # Nullable only for historical rows that could not be linked safely.
    lead_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_lead_analysis_organization_lead",
            ondelete="RESTRICT",
        ),
        Index("ix_lead_analysis_org_lead_created", "organization_id", "lead_id", "created_at", "id"),
    )

    company: Mapped[str] = mapped_column(
        String(200)
    )

    email: Mapped[str] = mapped_column(
        String(200)
    )

    priority: Mapped[str] = mapped_column(
        String(50)
    )

    lead_score: Mapped[int] = mapped_column(
        Integer
    )

    result: Mapped[dict] = mapped_column(
        JSON
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    organization = relationship(
        "Organization",
        backref="lead_analyses",
    )
