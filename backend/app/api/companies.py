from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import ContactHistory, ContactStatus
from app.schemas import CompanyOut, CompanyResolveIn, ContactOut, ContactUpdate
from app.services.company_identity import CompanyIdentityService
from app.services.exclusion import ExclusionEngine

router = APIRouter(prefix="/api", tags=["companies"])


@router.post("/companies/resolve", response_model=CompanyOut)
async def resolve_company(body: CompanyResolveIn, db: AsyncSession = Depends(get_db)):
    svc = CompanyIdentityService(db)
    company = await svc.resolve(body.name, domain=body.domain, country=body.country)
    await db.flush()
    await db.refresh(company)
    return company


@router.get("/companies", response_model=list[CompanyOut])
async def list_companies(db: AsyncSession = Depends(get_db)):
    from app.models import Company

    return list((await db.scalars(select(Company).order_by(Company.canonical_name))).all())


@router.put("/contacts", response_model=ContactOut)
async def upsert_contact(body: ContactUpdate, db: AsyncSession = Depends(get_db)):
    try:
        status = ContactStatus(body.status)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid status: {body.status}") from exc

    row = await db.scalar(
        select(ContactHistory).where(
            ContactHistory.company_id == body.company_id,
            ContactHistory.candidate_id == body.candidate_id,
        )
    )
    if not row:
        row = ContactHistory(
            company_id=body.company_id,
            candidate_id=body.candidate_id,
            status=status,
            notes=body.notes,
            contacted_at=datetime.now(timezone.utc) if status != ContactStatus.none else None,
        )
        db.add(row)
    else:
        row.status = status
        row.notes = body.notes
        if status != ContactStatus.none and not row.contacted_at:
            row.contacted_at = datetime.now(timezone.utc)

    await db.flush()
    engine = ExclusionEngine(db)
    await engine.reevaluate_for_contact_change(body.company_id, body.candidate_id)
    await db.refresh(row)
    return ContactOut(
        id=row.id,
        company_id=row.company_id,
        candidate_id=row.candidate_id,
        status=row.status.value,
        contacted_at=row.contacted_at,
        notes=row.notes,
    )


@router.get("/contacts", response_model=list[ContactOut])
async def list_contacts(candidate_id: UUID | None = None, db: AsyncSession = Depends(get_db)):
    q = select(ContactHistory)
    if candidate_id:
        q = q.where(ContactHistory.candidate_id == candidate_id)
    rows = (await db.scalars(q)).all()
    return [
        ContactOut(
            id=r.id,
            company_id=r.company_id,
            candidate_id=r.candidate_id,
            status=r.status.value,
            contacted_at=r.contacted_at,
            notes=r.notes,
        )
        for r in rows
    ]
