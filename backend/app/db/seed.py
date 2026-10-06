"""Seed system opportunity types and default source health rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OpportunityType, SourceHealth

SYSTEM_TYPES = [
    ("PFE", "PFE / Final Project", "PFE / Projet de fin d'études", "مشروع ختم الدروس"),
    ("PFE_STAGE", "PFE Internship", "Stage PFE", "تربص مشروع ختم الدروس"),
    ("END_OF_STUDIES", "End of Studies", "Fin d'études", "نهاية الدراسة"),
    ("SUMMER_INTERNSHIP", "Summer Internship", "Stage d'été", "تدريب صيفي"),
    ("INTERNSHIP", "Internship", "Stage", "تدريب"),
    ("GRADUATE", "Graduate", "Jeune diplômé", "خريج"),
    ("JUNIOR", "Junior", "Junior", "مبتدئ"),
    ("ENTRY_LEVEL", "Entry Level", "Débutant", "مستوى مبتدئ"),
    ("FULL_TIME", "Full Time", "Temps plein", "دوام كامل"),
    ("PART_TIME", "Part Time", "Temps partiel", "دوام جزئي"),
    ("CONTRACT", "Contract", "Contrat", "عقد"),
    ("FREELANCE", "Freelance", "Freelance", "عمل حر"),
    ("REMOTE_ONLY", "Remote Only", "Télétravail uniquement", "عن بُعد فقط"),
]

DEFAULT_SOURCES = ["remotive", "arbeitnow", "remoteok", "manual"]


async def seed_opportunity_types(session: AsyncSession) -> None:
    for code, en, fr, ar in SYSTEM_TYPES:
        existing = await session.scalar(
            select(OpportunityType).where(OpportunityType.code == code)
        )
        if existing:
            continue
        session.add(
            OpportunityType(
                code=code,
                label_en=en,
                label_fr=fr,
                label_ar=ar,
                is_system=True,
            )
        )
    await session.flush()


async def seed_source_health(session: AsyncSession) -> None:
    for name in DEFAULT_SOURCES:
        existing = await session.scalar(
            select(SourceHealth).where(SourceHealth.source_name == name)
        )
        if existing:
            continue
        session.add(SourceHealth(source_name=name))
    await session.flush()


async def run_startup_seeds(session: AsyncSession) -> None:
    await seed_opportunity_types(session)
    await seed_source_health(session)
    await session.commit()
