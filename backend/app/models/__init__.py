"""SQLAlchemy models for Hanicar Jobs."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class ContactStatus(str, enum.Enum):
    none = "none"
    contacted = "contacted"
    applied = "applied"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"


class OpportunityStatus(str, enum.Enum):
    new = "new"
    matched = "matched"
    suppressed = "suppressed"
    archived = "archived"


class ApplicationStatus(str, enum.Enum):
    draft = "draft"
    prepared = "prepared"
    queued = "queued"
    sent = "sent"
    applied = "applied"
    interviewing = "interviewing"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"
    failed = "failed"


class SearchRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class OpportunityType(Base):
    __tablename__ = "opportunity_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label_en: Mapped[str] = mapped_column(String(128))
    label_fr: Mapped[str] = mapped_column(String(128))
    label_ar: Mapped[str] = mapped_column(String(128))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="opportunity_type")


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    locale: Mapped[str] = mapped_column(String(8), default="en")  # en | fr | ar
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped[Optional["CandidateProfile"]] = relationship(
        back_populates="candidate", uselist=False, cascade="all, delete-orphan"
    )
    search_profiles: Mapped[list["SearchProfile"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), unique=True
    )
    cv_text: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="profile")


class SearchProfile(Base):
    __tablename__ = "search_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    keywords: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    locations: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    opportunity_type_codes: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate: Mapped["Candidate"] = relationship(back_populates="search_profiles")
    search_runs: Mapped[list["SearchRun"]] = relationship(back_populates="profile")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    canonical_name: Mapped[str] = mapped_column(String(255), index=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    country: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    embedding: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    aliases: Mapped[list["CompanyAlias"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    contacts: Mapped[list["ContactHistory"]] = relationship(back_populates="company")
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="company")


class CompanyAlias(Base):
    __tablename__ = "company_aliases"
    __table_args__ = (UniqueConstraint("alias", "alias_type", name="uq_alias_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(255), index=True)
    alias_type: Mapped[str] = mapped_column(String(32))  # domain | name

    company: Mapped["Company"] = relationship(back_populates="aliases")


class ContactHistory(Base):
    __tablename__ = "contact_history"
    __table_args__ = (
        UniqueConstraint("company_id", "candidate_id", name="uq_company_candidate_contact"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ContactStatus] = mapped_column(
        Enum(ContactStatus, name="contact_status"), default=ContactStatus.none
    )
    contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="contacts")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text, default="")
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    opportunity_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunity_types.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[OpportunityStatus] = mapped_column(
        Enum(OpportunityStatus, name="opportunity_status"),
        default=OpportunityStatus.new,
        index=True,
    )
    raw_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    match_reasons: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    skill_gaps: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Optional["Company"]] = relationship(back_populates="opportunities")
    opportunity_type: Mapped[Optional["OpportunityType"]] = relationship(
        back_populates="opportunities"
    )
    exclusion_decisions: Mapped[list["ExclusionDecision"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )


class ExclusionDecision(Base):
    __tablename__ = "exclusion_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    reason_code: Mapped[str] = mapped_column(String(64))
    reason_detail: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    opportunity: Mapped["Opportunity"] = relationship(back_populates="exclusion_decisions")


class SearchRun(Base):
    __tablename__ = "search_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_profiles.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[SearchRunStatus] = mapped_column(
        Enum(SearchRunStatus, name="search_run_status"), default=SearchRunStatus.pending
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    events: Mapped[list[Any]] = mapped_column(JSONB, default=list)

    profile: Mapped["SearchProfile"] = relationship(back_populates="search_runs")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"), default=ApplicationStatus.draft
    )
    draft_body: Mapped[str] = mapped_column(Text, default="")
    override_log: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    follow_up_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    interview_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    contact_name: Mapped[str] = mapped_column(String(255), default="")
    contact_email: Mapped[str] = mapped_column(String(320), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LlmRequest(Base):
    __tablename__ = "llm_requests"
    __table_args__ = (
        UniqueConstraint("input_hash", "model", "prompt_version", name="uq_llm_cache"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(32), default="v1")
    response: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceHealth(Base):
    __tablename__ = "source_health"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
