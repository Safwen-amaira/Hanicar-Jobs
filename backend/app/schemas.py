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
    manual_recontact_override: bool = False


class ApplicationOut(BaseModel):
    id: UUID
    opportunity_id: UUID
    candidate_id: UUID
    status: str
    draft_body: str
    override_log: list[Any]
    follow_up_due_at: Optional[datetime]
    applied_at: Optional[datetime] = None
    interview_at: Optional[datetime] = None
    decision_at: Optional[datetime] = None
    next_action_at: Optional[datetime] = None
    contact_name: str = ""
    contact_email: str = ""
    notes: str = ""
    created_at: datetime
    updated_at: Optional[datetime] = None
    opportunity_title: Optional[str] = None
    company_name: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ApplicationStatusUpdate(BaseModel):
    status: Optional[str] = None
    override_notes: str = ""
    follow_up_due_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    interview_at: Optional[datetime] = None
    decision_at: Optional[datetime] = None
    next_action_at: Optional[datetime] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None


class ApplicationRegenerateIn(BaseModel):
    instructions: str = ""
    tone: str = "concise"
    include_email_subject: bool = True


class ApplicationContactDiscoveryOut(BaseModel):
    application_id: UUID
    emails: list[str] = Field(default_factory=list)
    apply_urls: list[str] = Field(default_factory=list)
    selected_email: str = ""
    note: str = ""


class ApplicationBatchSendIn(BaseModel):
    max_to_send: int = Field(default=5, ge=1, le=50)
    delay_seconds: float = Field(default=8.0, ge=0.0, le=3600.0)
    statuses: list[str] = Field(default_factory=lambda: ["prepared", "queued"])
    smtp: Optional["SmtpSettingsIn"] = None
    attach_cv: bool = True
    attach_cover_letter: bool = True
    dry_run: bool = True
    manual_recontact_override: bool = False
    human_verified_ids: list[UUID] = Field(default_factory=list)


class ApplicationBatchSendOut(BaseModel):
    attempted: int = 0
    sent: int = 0
    skipped: int = 0
    dry_run: bool = True
    results: list[dict[str, Any]] = Field(default_factory=list)


class ApplicationBatchPrepareIn(BaseModel):
    max_to_prepare: int = Field(default=8, ge=1, le=50)
    statuses: list[str] = Field(default_factory=lambda: ["draft", "prepared", "queued"])
    persist_contacts: bool = True
    polish_with_llm: bool = True


class ApplicationBatchPrepareOut(BaseModel):
    attempted: int = 0
    queued: int = 0
    needs_review: int = 0
    skipped: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)


class ApplicationAutoQueueIn(BaseModel):
    candidate_id: UUID
    min_score: float = Field(default=55.0, ge=0, le=100)
    max_to_draft: int = Field(default=8, ge=1, le=40)
    polish_with_llm: bool = True


class ApplicationAutoQueueOut(BaseModel):
    created: int = 0
    skipped: int = 0
    application_ids: list[str] = Field(default_factory=list)
    queued: int = 0
    needs_review: int = 0
    prepare_skipped: int = 0
    note: str = ""


class OpportunityWebSearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=240)
    locations: list[str] = Field(default_factory=list)
    candidate_id: Optional[UUID] = None
    limit: int = Field(default=40, ge=1, le=120)


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
    warnings: list[str] = Field(default_factory=list)
    ready: bool = False


class ApplicationEmailSendIn(BaseModel):
    to: EmailStr
    subject: str
    body: str
    smtp: Optional[SmtpSettingsIn] = None
    attach_cv: bool = True
    attach_cover_letter: bool = True
    manual_recontact_override: bool = False
    human_verified: bool = False
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
    llm_provider: str = "mock"
    llm_model: str = "mock"
    llm_live: bool = False
    human_in_the_loop: bool = True
    auto_send: bool = False
    llm_hint: str = ""
    auto_draft_enabled: bool = True
    auto_polish_with_llm: bool = True


class LlmPingOut(BaseModel):
    ok: bool
    live: bool
    provider: str
    model: str
    sample: str = ""
    human_in_the_loop: bool = True
    auto_send: bool = False
    hint: str = ""


class MatchPreviewOut(BaseModel):
    score: float
    reasons: list[str]
    skill_gaps: list[str]


class LlmStatusOut(BaseModel):
    ai_enabled: bool
    requested_provider: str = "auto"
    provider: str
    model: str
    live: bool
    human_in_the_loop: bool = True
    auto_send: bool = False
    auto_draft_enabled: bool = True
    auto_polish_with_llm: bool = True
    chain: list[str] = []
    hint: str = ""
