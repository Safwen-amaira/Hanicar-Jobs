"""Celery tasks - scheduled health and optional search runs."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.workers.celery_app import celery_app


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(name="app.workers.tasks.ping_sources")
def ping_sources() -> dict:
    async def _inner():
        from sqlalchemy import select

        from app.db.session import AsyncSessionLocal
        from app.models import SourceHealth

        async with AsyncSessionLocal() as session:
            rows = (await session.scalars(select(SourceHealth))).all()
            return {
                "ts": datetime.now(timezone.utc).isoformat(),
                "sources": [r.source_name for r in rows],
            }

    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_inner())
        finally:
            loop.close()
    except Exception as exc:
        return {"error": str(exc)}


@celery_app.task(name="app.workers.tasks.run_search")
def run_search(profile_id: str) -> dict:
    async def _inner():
        from uuid import UUID

        from app.db.session import AsyncSessionLocal
        from app.services.pipeline import SearchPipeline

        async with AsyncSessionLocal() as session:
            pipeline = SearchPipeline(session)
            run = await pipeline.run(UUID(profile_id))
            return {"run_id": str(run.id), "status": run.status.value, "stats": run.stats}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_inner())
    finally:
        loop.close()
