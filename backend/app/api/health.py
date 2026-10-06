from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas import HealthOut

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthOut)
async def health() -> HealthOut:
    settings = get_settings()
    return HealthOut(
        status="ok",
        service="hanicar-jobs",
        version=__version__,
        tagline=settings.tagline,
        ai_enabled=settings.ai_enabled,
    )


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict:
    settings = get_settings()
    checks: dict = {"database": False, "redis": False}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as exc:
        checks["database_error"] = str(exc)
    try:
        r = redis_from_url(settings.redis_url)
        pong = await r.ping()
        checks["redis"] = bool(pong)
        await r.aclose()
    except Exception as exc:
        checks["redis_error"] = str(exc)
    ok = checks["database"] and checks["redis"]
    return {
        "status": "ready" if ok else "degraded",
        "checks": checks,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
