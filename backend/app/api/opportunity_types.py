from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import OpportunityType
from app.schemas import OpportunityTypeCreate, OpportunityTypeOut

router = APIRouter(prefix="/api/opportunity-types", tags=["opportunity-types"])


@router.get("", response_model=list[OpportunityTypeOut])
async def list_types(db: AsyncSession = Depends(get_db)) -> list[OpportunityType]:
    rows = (await db.scalars(select(OpportunityType).order_by(OpportunityType.code))).all()
    return list(rows)


@router.post("", response_model=OpportunityTypeOut, status_code=201)
async def create_type(
    body: OpportunityTypeCreate, db: AsyncSession = Depends(get_db)
) -> OpportunityType:
    code = body.code.strip().upper().replace(" ", "_")
    existing = await db.scalar(select(OpportunityType).where(OpportunityType.code == code))
    if existing:
        raise HTTPException(400, "Opportunity type code already exists")
    row = OpportunityType(
        code=code,
        label_en=body.label_en or code,
        label_fr=body.label_fr or body.label_en or code,
        label_ar=body.label_ar or body.label_en or code,
        is_system=False,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row
