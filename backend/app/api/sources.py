from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import SourceHealth
from app.schemas import SourceHealthOut

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("/health", response_model=list[SourceHealthOut])
async def source_health(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(SourceHealth).order_by(SourceHealth.source_name))).all()
    out = []
    for r in rows:
        total = (r.success_count or 0) + (r.error_count or 0)
        rate = (r.success_count / total) if total else 0.0
        out.append(
            SourceHealthOut(
                source_name=r.source_name,
                last_run=r.last_run,
                success_count=r.success_count,
                error_count=r.error_count,
                last_error=r.last_error,
                success_rate=round(rate, 3),
            )
        )
    return out
