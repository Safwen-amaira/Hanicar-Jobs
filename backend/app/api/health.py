from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import get_settings
from app.db.session import get_db
from app.llm.providers import CachedLLM, is_fallback_text, llm_status
from app.schemas import HealthOut, LlmPingOut, LlmStatusOut

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthOut)
async def health() -> HealthOut:
    settings = get_settings()
    status = llm_status()
    return HealthOut(
        status="ok",
        service="hanicar-jobs",
        version=__version__,
        tagline=settings.tagline,
        ai_enabled=settings.ai_enabled,
        llm_provider=status["provider"],
        llm_model=str(status["model"]),
        llm_live=bool(status["live"]),
        human_in_the_loop=True,
        auto_send=False,
        llm_hint=str(status["hint"]),
        auto_draft_enabled=bool(status["auto_draft_enabled"]),
        auto_polish_with_llm=bool(status["auto_polish_with_llm"]),
    )


@router.get("/llm", response_model=LlmPingOut)
async def llm_ping(db: AsyncSession = Depends(get_db)) -> LlmPingOut:
    status = llm_status()
    llm = CachedLLM(db)
    sample = await llm.complete(
        "Reply with the single word READY. Do not add punctuation or extra text.",
        system="You are a connectivity probe. Answer with one word.",
    )
    live = not is_fallback_text(sample)
    return LlmPingOut(
        ok=live,
        live=live,
        provider=getattr(llm.provider, "name", status["provider"]),
        model=str(getattr(llm.provider, "model", status["model"])),
        sample=(sample or "")[:280],
        human_in_the_loop=True,
        auto_send=False,
        hint=status["hint"] if live else "Live LLM did not respond; drafts will use the local template until a provider is reachable.",
    )


@router.get("/llm-status", response_model=LlmStatusOut)
async def llm_status_endpoint() -> LlmStatusOut:
    """Return the full LLM provider chain and live status without making an LLM call."""
    status = llm_status()
    return LlmStatusOut(
        ai_enabled=bool(status["ai_enabled"]),
        requested_provider=str(status["requested_provider"]),
        provider=str(status["provider"]),
        model=str(status["model"]),
        live=bool(status["live"]),
        human_in_the_loop=True,
        auto_send=False,
        auto_draft_enabled=bool(status["auto_draft_enabled"]),
        auto_polish_with_llm=bool(status["auto_polish_with_llm"]),
        chain=list(status.get("chain") or []),
        hint=str(status["hint"]),
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
