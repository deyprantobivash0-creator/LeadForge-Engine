from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class Lead(Base):
    __tablename__ = "leads"

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

    organization = relationship(
        "Organization",
        backref="leads",
    )

    company: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    industry: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    lead_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    priority: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    ai_reason: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    next_action: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="New",
        index=True,
    )

    processing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    last_contacted: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    next_follow_up: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "email",
            name="uq_leads_organization_email",
        ),
        Index(
            "ix_leads_org_created",
            "organization_id",
            "created_at",
        ),
        Index(
            "ix_leads_org_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_leads_org_followup",
            "organization_id",
            "next_follow_up",
        ),
    )