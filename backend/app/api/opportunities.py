import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models import ExclusionDecision, Opportunity, OpportunityStatus, SearchRun
from app.schemas import ExclusionOut, OpportunityOut, SearchRunOut
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
