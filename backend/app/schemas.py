"""Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class OpportunityTypeOut(BaseModel):
    id: UUID
    code: str
    label_en: str
    label_fr: str
    label_ar: str
    is_system: bool

    model_config = {"from_attributes": True}


class OpportunityTypeCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    label_en: str
    label_fr: str = ""
    label_ar: str = ""


class CandidateCreate(BaseModel):
    name: str
    email: EmailStr
    locale: str = "en"


class CandidateOut(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    locale: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateProfileUpdate(BaseModel):
    cv_text: str = ""
    skills: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)


class CandidateCvAttachmentUpdate(BaseModel):
    filename: str
    content_type: str = "application/pdf"
    data_base64: str


class CandidateProfileOut(BaseModel):
    id: UUID
    candidate_id: UUID
    cv_text: str
    skills: list[Any]
    preferences: dict[str, Any]

    model_config = {"from_attributes": True}


class SearchProfileCreate(BaseModel):
    candidate_id: UUID
    name: str
    keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    opportunity_type_codes: list[str] = Field(default_factory=list)
    active: bool = True


class SearchProfileOut(BaseModel):
    id: UUID
    candidate_id: UUID
    name: str
    keywords: list[Any]
    locations: list[Any]
    opportunity_type_codes: list[Any]
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyResolveIn(BaseModel):
    name: str
    domain: Optional[str] = None
    country: Optional[str] = None


class CompanyOut(BaseModel):
    id: UUID
    canonical_name: str
    domain: Optional[str]
    country: Optional[str]

    model_config = {"from_attributes": True}


class ContactUpdate(BaseModel):
    company_id: UUID
    candidate_id: UUID
    status: str
    notes: str = ""


class ContactOut(BaseModel):
    id: UUID
    company_id: UUID
    candidate_id: UUID
    status: str
    contacted_at: Optional[datetime]
    notes: str

    model_config = {"from_attributes": True}


class OpportunityOut(BaseModel):
    id: UUID
    title: str
    description: str
    company_id: Optional[UUID]
    company_name: Optional[str] = None
    opportunity_type_id: Optional[UUID]
    opportunity_type_code: Optional[str] = None
    source: str
    source_url: Optional[str]
    location: Optional[str]
    remote: bool
    deadline: Optional[date]
    status: str
    match_score: Optional[float]
    match_reasons: list[Any] = Field(default_factory=list)
    skill_gaps: list[Any] = Field(default_factory=list)
    exclusion_reasons: list[dict[str, Any]] = Field(default_factory=list)
    collected_at: datetime

    model_config = {"from_attributes": True}


class ExclusionOut(BaseModel):
    id: UUID
    opportunity_id: UUID
    reason_code: str
    reason_detail: str
    decided_at: datetime

    model_config = {"from_attributes": True}


class SearchRunOut(BaseModel):
    id: UUID
    profile_id: UUID
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    stats: dict[str, Any]
    events: list[Any] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ApplicationCreate(BaseModel):
    opportunity_id: UUID
    candidate_id: UUID
    override_notes: str = ""


class ApplicationOut(BaseModel):
    id: UUID
    opportunity_id: UUID
    candidate_id: UUID
    status: str
    draft_body: str
    override_log: list[Any]
    follow_up_due_at: Optional[datetime]
    created_at: datetime
    opportunity_title: Optional[str] = None
    company_name: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ApplicationStatusUpdate(BaseModel):
    status: str  # kanban column: draft|queued|sent|failed or custom pipeline labels
    override_notes: str = ""


class SmtpSettingsIn(BaseModel):
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = ""
    from_name: str = ""
    use_tls: bool = True


class SmtpTestOut(BaseModel):
    ok: bool
    status: str
    detail: str


class ApplicationEmailComposeOut(BaseModel):
    application_id: UUID
    to: str
    subject: str
    body: str
    suggested_attachments: list[dict[str, Any]] = Field(default_factory=list)


class ApplicationEmailSendIn(BaseModel):
    to: EmailStr
    subject: str
    body: str
    smtp: Optional[SmtpSettingsIn] = None
    attach_cv: bool = True
    attach_cover_letter: bool = True
    extra_attachments: list[CandidateCvAttachmentUpdate] = Field(default_factory=list)


class ApplicationEmailSendOut(BaseModel):
    sent: bool
    status: str
    detail: str
    attachments: list[str] = Field(default_factory=list)


class SourceHealthOut(BaseModel):
    source_name: str
    last_run: Optional[datetime]
    success_count: int
    error_count: int
    last_error: Optional[str]
    success_rate: float = 0.0

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str
    service: str
    version: str
    tagline: str
    ai_enabled: bool


class MatchPreviewOut(BaseModel):
    score: float
    reasons: list[str]
    skill_gaps: list[str]
