from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models import Candidate, CandidateProfile, SearchProfile
from app.schemas import (
    CandidateCreate,
    CandidateCvAttachmentUpdate,
    CandidateOut,
    CandidateProfileOut,
    CandidateProfileUpdate,
    SearchProfileCreate,
    SearchProfileOut,
)

router = APIRouter(prefix="/api", tags=["candidates"])


@router.post("/candidates", response_model=CandidateOut, status_code=201)
async def create_candidate(body: CandidateCreate, db: AsyncSession = Depends(get_db)) -> Candidate:
    existing = await db.scalar(select(Candidate).where(Candidate.email == body.email))
    if existing:
        raise HTTPException(400, "Email already registered")
    if body.locale not in {"en", "fr", "ar"}:
        raise HTTPException(400, "locale must be en, fr, or ar")
    cand = Candidate(name=body.name, email=str(body.email), locale=body.locale)
    db.add(cand)
    await db.flush()
    db.add(CandidateProfile(candidate_id=cand.id, cv_text="", skills=[], preferences={}))
    await db.flush()
    await db.refresh(cand)
    return cand


@router.get("/candidates", response_model=list[CandidateOut])
async def list_candidates(db: AsyncSession = Depends(get_db)) -> list[Candidate]:
    return list((await db.scalars(select(Candidate).order_by(Candidate.created_at.desc()))).all())


@router.get("/candidates/{candidate_id}", response_model=CandidateOut)
async def get_candidate(candidate_id: UUID, db: AsyncSession = Depends(get_db)) -> Candidate:
    cand = await db.get(Candidate, candidate_id)
    if not cand:
        raise HTTPException(404, "Not found")
    return cand


@router.put("/candidates/{candidate_id}/profile", response_model=CandidateProfileOut)
async def update_profile(
    candidate_id: UUID, body: CandidateProfileUpdate, db: AsyncSession = Depends(get_db)
) -> CandidateProfile:
    profile = await db.scalar(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id)
    )
    if not profile:
        raise HTTPException(404, "Profile not found")
    profile.cv_text = body.cv_text
    profile.skills = body.skills
    profile.preferences = body.preferences
    await db.flush()
    await db.refresh(profile)
    return profile


@router.get("/candidates/{candidate_id}/profile", response_model=CandidateProfileOut)
async def get_profile(candidate_id: UUID, db: AsyncSession = Depends(get_db)) -> CandidateProfile:
    profile = await db.scalar(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id)
    )
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile


@router.put("/candidates/{candidate_id}/cv-attachment", response_model=CandidateProfileOut)
async def update_cv_attachment(
    candidate_id: UUID, body: CandidateCvAttachmentUpdate, db: AsyncSession = Depends(get_db)
) -> CandidateProfile:
    profile = await db.scalar(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id)
    )
    if not profile:
        raise HTTPException(404, "Profile not found")
    if body.content_type not in {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
        raise HTTPException(400, "CV attachment must be PDF, DOC, or DOCX")
    profile.preferences = {
        **(profile.preferences or {}),
        "cv_attachment": {
            "filename": body.filename[:180],
            "content_type": body.content_type,
            "data_base64": body.data_base64,
        },
    }
    await db.flush()
    await db.refresh(profile)
    return profile


@router.put("/candidates/{candidate_id}/cover-letter-attachment", response_model=CandidateProfileOut)
async def update_cover_letter_attachment(
    candidate_id: UUID, body: CandidateCvAttachmentUpdate, db: AsyncSession = Depends(get_db)
) -> CandidateProfile:
    profile = await db.scalar(
        select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id)
    )
    if not profile:
        raise HTTPException(404, "Profile not found")
    if body.content_type != "application/pdf":
        raise HTTPException(400, "Cover letter attachment must be a PDF")
    profile.preferences = {
        **(profile.preferences or {}),
        "cover_letter_attachment": {
            "filename": body.filename[:180],
            "content_type": body.content_type,
            "data_base64": body.data_base64,
        },
    }
    await db.flush()
    await db.refresh(profile)
    return profile


@router.post("/search-profiles", response_model=SearchProfileOut, status_code=201)
async def create_search_profile(
    body: SearchProfileCreate, db: AsyncSession = Depends(get_db)
) -> SearchProfile:
    cand = await db.get(Candidate, body.candidate_id)
    if not cand:
        raise HTTPException(404, "Candidate not found")
    sp = SearchProfile(
        candidate_id=body.candidate_id,
        name=body.name,
        keywords=body.keywords,
        locations=body.locations,
        opportunity_type_codes=[c.upper() for c in body.opportunity_type_codes],
        active=body.active,
    )
    db.add(sp)
    await db.flush()
    await db.refresh(sp)
    return sp


@router.get("/search-profiles", response_model=list[SearchProfileOut])
async def list_search_profiles(
    candidate_id: UUID | None = None, db: AsyncSession = Depends(get_db)
) -> list[SearchProfile]:
    q = select(SearchProfile).order_by(SearchProfile.created_at.desc())
    if candidate_id:
        q = q.where(SearchProfile.candidate_id == candidate_id)
    return list((await db.scalars(q)).all())


@router.get("/search-profiles/{profile_id}", response_model=SearchProfileOut)
async def get_search_profile(profile_id: UUID, db: AsyncSession = Depends(get_db)) -> SearchProfile:
    sp = await db.get(SearchProfile, profile_id)
    if not sp:
        raise HTTPException(404, "Not found")
    return sp
