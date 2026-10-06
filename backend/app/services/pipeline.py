"""Search pipeline: collect → identity → dedupe → exclude → match → persist. Emits SSE events."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.collectors.base import BaseCollector, RawOpportunity, default_collectors
from app.models import (
    CandidateProfile,
    Opportunity,
    OpportunityStatus,
    OpportunityType,
    SearchProfile,
    SearchRun,
    SearchRunStatus,
    SourceHealth,
)
from app.services.company_identity import CompanyIdentityService
from app.services.exclusion import ExclusionEngine
from app.services.matching import MatchingService


EventCallback = Callable[[dict[str, Any]], None]


class SearchPipeline:
    def __init__(self, session: AsyncSession, collectors: list[BaseCollector] | None = None):
        self.session = session
        self.collectors = collectors or default_collectors()
        self.identity = CompanyIdentityService(session)
        self.exclusion = ExclusionEngine(session)
        self.matching = MatchingService(self.exclusion)

    async def run(
        self,
        profile_id: UUID,
        *,
        on_event: EventCallback | None = None,
    ) -> SearchRun:
        profile = await self.session.get(SearchProfile, profile_id)
        if not profile:
            raise ValueError("Search profile not found")

        run = SearchRun(profile_id=profile_id, status=SearchRunStatus.running, started_at=datetime.now(timezone.utc), events=[])
        self.session.add(run)
        await self.session.flush()

        def emit(event: dict[str, Any]) -> None:
            event = {**event, "ts": datetime.now(timezone.utc).isoformat(), "run_id": str(run.id)}
            run.events = [*(run.events or []), event]
            if on_event:
                on_event(event)

        emit({"type": "started", "message": "SEARCH NOW sequence started"})

        candidate_profile = await self.session.scalar(
            select(CandidateProfile).where(CandidateProfile.candidate_id == profile.candidate_id)
        )
        type_map = {
            t.code: t
            for t in (
                await self.session.scalars(select(OpportunityType))
            ).all()
        }

        stats = {"collected": 0, "new": 0, "duplicates": 0, "suppressed": 0, "errors": 0}
        try:
            for collector in self.collectors:
                emit({"type": "source_start", "source": collector.name})
                try:
                    raws = await collector.collect(profile.keywords or [], profile.locations or [])
                    await self._record_source(collector.name, ok=True)
                except Exception as exc:
                    stats["errors"] += 1
                    await self._record_source(collector.name, ok=False, error=str(exc))
                    emit({"type": "source_error", "source": collector.name, "error": str(exc)})
                    continue

                for raw in raws:
                    stats["collected"] += 1
                    # Soft filter by opportunity types on profile
                    hint = raw.opportunity_type_hint
                    if profile.opportunity_type_codes and hint:
                        if hint not in profile.opportunity_type_codes and "REMOTE_ONLY" not in profile.opportunity_type_codes:
                            # still allow remotes through if remote
                            if not (raw.remote and "REMOTE_ONLY" in profile.opportunity_type_codes):
                                if hint not in profile.opportunity_type_codes:
                                    pass  # keep collecting broadly; ranking handles fit

                    existing = await self.session.scalar(
                        select(Opportunity).where(Opportunity.raw_hash == raw.content_hash())
                    )
                    if existing:
                        stats["duplicates"] += 1
                        emit({
                            "type": "duplicate",
                            "title": raw.title,
                            "company": raw.company_name,
                            "opportunity_id": str(existing.id),
                        })
                        continue

                    company = await self.identity.resolve(
                        raw.company_name, domain=raw.company_domain, country=raw.country
                    )
                    ot = type_map.get(hint) if hint else None
                    opp = Opportunity(
                        title=raw.title[:512],
                        description=raw.description,
                        company_id=company.id,
                        opportunity_type_id=ot.id if ot else None,
                        source=raw.source,
                        source_url=raw.source_url,
                        location=raw.location,
                        remote=raw.remote,
                        status=OpportunityStatus.new,
                        raw_hash=raw.content_hash(),
                    )
                    self.session.add(opp)
                    await self.session.flush()

                    decisions = await self.exclusion.evaluate_opportunity(
                        opp, candidate_id=profile.candidate_id
                    )
                    match = self.matching.score(opp, profile, candidate_profile)
                    opp.match_score = match.score
                    opp.match_reasons = match.reasons
                    opp.skill_gaps = match.skill_gaps
                    if opp.status != OpportunityStatus.suppressed:
                        opp.status = OpportunityStatus.matched

                    if decisions:
                        stats["suppressed"] += 1
                        emit({
                            "type": "suppressed",
                            "title": opp.title,
                            "company": company.canonical_name,
                            "reasons": [d.reason_code for d in decisions],
                            "opportunity_id": str(opp.id),
                        })
                    else:
                        stats["new"] += 1
                        emit({
                            "type": "opportunity",
                            "title": opp.title,
                            "company": company.canonical_name,
                            "score": match.score,
                            "opportunity_id": str(opp.id),
                        })

                emit({"type": "source_done", "source": collector.name, "count": len(raws)})

            run.status = SearchRunStatus.completed
            run.stats = stats
            run.finished_at = datetime.now(timezone.utc)
            from app.core.config import get_settings
            from app.services.applications import ApplicationService

            settings = get_settings()
            if settings.auto_draft_enabled:
                queued = await ApplicationService(self.session).automate_for_human_review(
                    candidate_id=profile.candidate_id,
                    min_score=settings.auto_draft_min_score,
                    max_to_draft=settings.auto_draft_limit,
                    polish_with_llm=settings.auto_polish_with_llm,
                    prepare=settings.auto_prepare_enabled,
                )
                stats["auto_drafted"] = queued["created"]
                stats["queued_for_review"] = queued.get("queued", 0)
                stats["needs_human_fix"] = queued.get("needs_review", 0)
                run.stats = stats
                emit({"type": "auto_drafted", "message": "High-score matches prepared for human review", **queued})
            emit({"type": "completed", "stats": stats})
        except Exception as exc:
            run.status = SearchRunStatus.failed
            run.stats = {**stats, "error": str(exc)}
            run.finished_at = datetime.now(timezone.utc)
            emit({"type": "failed", "error": str(exc)})
            raise
        finally:
            await self.session.flush()
        return run

    async def _record_source(self, name: str, *, ok: bool, error: str | None = None) -> None:
        row = await self.session.scalar(select(SourceHealth).where(SourceHealth.source_name == name))
        if not row:
            row = SourceHealth(source_name=name)
            self.session.add(row)
            await self.session.flush()
        row.last_run = datetime.now(timezone.utc)
        if ok:
            row.success_count = (row.success_count or 0) + 1
            row.last_error = None
        else:
            row.error_count = (row.error_count or 0) + 1
            row.last_error = (error or "")[:2000]


# In-memory event bus for SSE (single-process; fine for compose default)
_run_queues: dict[str, asyncio.Queue] = {}


def get_run_queue(run_id: str) -> asyncio.Queue:
    if run_id not in _run_queues:
        _run_queues[run_id] = asyncio.Queue()
    return _run_queues[run_id]


async def stream_run_events(run_id: str) -> AsyncIterator[dict[str, Any]]:
    q = get_run_queue(run_id)
    while True:
        event = await q.get()
        yield event
        if event.get("type") in {"completed", "failed"}:
            break
