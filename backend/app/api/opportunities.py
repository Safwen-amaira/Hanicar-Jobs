import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import get_db
from app.models import CandidateProfile, ExclusionDecision, Opportunity, OpportunityStatus, SearchProfile, SearchRun
from app.schemas import ExclusionOut, OpportunityOut, OpportunityWebSearchIn, SearchRunOut
from app.services.company_identity import CompanyIdentityService
from app.services.exclusion import ExclusionEngine
from app.services.matching import MatchingService
from app.services.pipeline import SearchPipeline, get_run_queue

router = APIRouter(prefix="/api", tags=["opportunities"])


def _opp_out(opp: Opportunity) -> OpportunityOut:
    return OpportunityOut(
        id=opp.id,
        title=opp.title,
        description=opp.description,
        company_id=opp.company_id,
        company_name=opp.company.canonical_name if opp.company else None,
        opportunity_type_id=opp.opportunity_type_id,
        opportunity_type_code=opp.opportunity_type.code if opp.opportunity_type else None,
        source=opp.source,
        source_url=opp.source_url,
        location=opp.location,
        remote=opp.remote,
        deadline=opp.deadline,
        status=opp.status.value,
        match_score=opp.match_score,
        match_reasons=opp.match_reasons or [],
        skill_gaps=opp.skill_gaps or [],
        exclusion_reasons=[
            {"code": d.reason_code, "detail": d.reason_detail}
            for d in (opp.exclusion_decisions or [])
        ],
        collected_at=opp.collected_at,
    )


@router.get("/opportunities", response_model=list[OpportunityOut])
async def list_opportunities(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Opportunity)
        .options(
            selectinload(Opportunity.company),
            selectinload(Opportunity.opportunity_type),
            selectinload(Opportunity.exclusion_decisions),
        )
        .order_by(Opportunity.match_score.desc().nullslast(), Opportunity.collected_at.desc())
    )
    if status:
        try:
            q = q.where(Opportunity.status == OpportunityStatus(status))
        except ValueError as exc:
            raise HTTPException(400, "Invalid status") from exc
    rows = (await db.scalars(q)).all()
    return [_opp_out(o) for o in rows]


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityOut)
async def get_opportunity(opportunity_id: UUID, db: AsyncSession = Depends(get_db)):
    opp = await db.scalar(
        select(Opportunity)
        .options(
            selectinload(Opportunity.company),
            selectinload(Opportunity.opportunity_type),
            selectinload(Opportunity.exclusion_decisions),
        )
        .where(Opportunity.id == opportunity_id)
    )
    if not opp:
        raise HTTPException(404, "Not found")
    return _opp_out(opp)


@router.post("/opportunities/web-search", response_model=list[OpportunityOut])
async def web_search_opportunities(body: OpportunityWebSearchIn, db: AsyncSession = Depends(get_db)):
    keywords = [part.strip() for part in body.query.replace(",", " ").split() if part.strip()]
    collectors = default_collectors()
    identity = CompanyIdentityService(db)
    exclusion = ExclusionEngine(db)
    matching = MatchingService(exclusion)
    candidate_profile = None
    synthetic_profile = None
    if body.candidate_id:
        candidate_profile = await db.scalar(
            select(CandidateProfile).where(CandidateProfile.candidate_id == body.candidate_id)
        )
        synthetic_profile = SearchProfile(
            candidate_id=body.candidate_id,
            name=f"Web search: {body.query[:80]}",
            keywords=keywords,
            locations=body.locations,
            opportunity_type_codes=[],
        )
    persisted: list[Opportunity] = []
    for collector in collectors:
        try:
            raws = await collector.collect(keywords, body.locations)
        except Exception:
            continue
        for raw in raws:
            if len(persisted) >= body.limit:
                break
            existing = await db.scalar(select(Opportunity).where(Opportunity.raw_hash == raw.content_hash()))
            if existing:
                persisted.append(existing)
                continue
            company = await identity.resolve(raw.company_name, domain=raw.company_domain, country=raw.country)
            opp = Opportunity(
                title=raw.title[:512],
                description=raw.description,
                company_id=company.id,
                source=raw.source,
                source_url=raw.source_url,
                location=raw.location,
                remote=raw.remote,
                status=OpportunityStatus.new,
                raw_hash=raw.content_hash(),
            )
            db.add(opp)
            await db.flush()
            if synthetic_profile is not None:
                decisions = await exclusion.evaluate_opportunity(opp, candidate_id=body.candidate_id)
                match = matching.score(opp, synthetic_profile, candidate_profile)
                opp.match_score = match.score
                opp.match_reasons = match.reasons
                opp.skill_gaps = match.skill_gaps
                if decisions:
                    opp.status = OpportunityStatus.suppressed
                else:
                    opp.status = OpportunityStatus.matched
            persisted.append(opp)
        if len(persisted) >= body.limit:
            break
    await db.commit()
    settings = get_settings()
    if body.candidate_id and settings.auto_draft_enabled:
        from app.services.applications import ApplicationService

        await ApplicationService(db).automate_for_human_review(
            candidate_id=body.candidate_id,
            min_score=settings.auto_draft_min_score,
            max_to_draft=settings.auto_draft_limit,
            polish_with_llm=settings.auto_polish_with_llm,
            prepare=settings.auto_prepare_enabled,
        )
        await db.commit()
    ids = [opp.id for opp in persisted]
    rows = (
        await db.scalars(
            select(Opportunity)
            .options(
                selectinload(Opportunity.company),
                selectinload(Opportunity.opportunity_type),
                selectinload(Opportunity.exclusion_decisions),
            )
            .where(Opportunity.id.in_(ids))
            .order_by(Opportunity.match_score.desc().nullslast(), Opportunity.collected_at.desc())
        )
    ).all()
    return [_opp_out(o) for o in rows]


@router.get("/suppressed", response_model=list[OpportunityOut])
async def list_suppressed(db: AsyncSession = Depends(get_db)):
    return await list_opportunities(status="suppressed", db=db)


@router.get("/exclusions", response_model=list[ExclusionOut])
async def list_exclusions(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(select(ExclusionDecision).order_by(ExclusionDecision.decided_at.desc()))
    ).all()
    return list(rows)


@router.post("/search/{profile_id}/run", response_model=SearchRunOut)
async def start_search(profile_id: UUID, db: AsyncSession = Depends(get_db)):
    pipeline = SearchPipeline(db)
    events_buffer: list = []

    def on_event(event: dict) -> None:
        events_buffer.append(event)

    run = await pipeline.run(profile_id, on_event=on_event)
    q = get_run_queue(str(run.id))
    for e in events_buffer:
        await q.put(e)
    return SearchRunOut(
        id=run.id,
        profile_id=run.profile_id,
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        stats=run.stats or {},
        events=run.events or [],
    )


@router.get("/search/runs/{run_id}", response_model=SearchRunOut)
async def get_run(run_id: UUID, db: AsyncSession = Depends(get_db)):
    run = await db.get(SearchRun, run_id)
    if not run:
        raise HTTPException(404, "Not found")
    return SearchRunOut(
        id=run.id,
        profile_id=run.profile_id,
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        stats=run.stats or {},
        events=run.events or [],
    )


@router.get("/search/runs/{run_id}/events")
async def sse_events(run_id: UUID, db: AsyncSession = Depends(get_db)):
    run = await db.get(SearchRun, run_id)
    if not run:
        raise HTTPException(404, "Not found")

    async def gen():
        for event in run.events or []:
            yield f"data: {json.dumps(event)}\n\n"
        if run.status.value in {"completed", "failed"}:
            return
        q = get_run_queue(str(run_id))
        while True:
            event = await q.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") in {"completed", "failed"}:
                break

    return StreamingResponse(gen(), media_type="text/event-stream")
