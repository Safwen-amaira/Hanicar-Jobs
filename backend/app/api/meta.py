from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("")
async def meta():
    settings = get_settings()
    return {
        "name": settings.app_name,
        "tagline": settings.tagline,
        "copyright": settings.copyright,
        "ai_enabled": settings.ai_enabled,
        "llm_provider": settings.llm_provider if settings.ai_enabled else "off",
        "multi_user": settings.multi_user,
        "locales": ["en", "fr", "ar"],
        "notice": "Derived from PFE Hunter concept by Safwen Amaira / Born as root.",
    }
