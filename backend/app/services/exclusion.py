"""Exclusion engine: suppress opportunities for contacted companies with explainable reasons."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models import (
    ContactHistory,
    ContactStatus,
    ExclusionDecision,
    Opportunity,
    OpportunityStatus,
)

SUPPRESSING_STATUSES = {
    ContactStatus.contacted,
    ContactStatus.applied,
    ContactStatus.interview,
    ContactStatus.offer,
    ContactStatus.rejected,
    ContactStatus.withdrawn,
}


class ExclusionEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def evaluate_opportunity(
        self,
        opportunity: Opportunity,
        candidate_id: Optional[UUID] = None,
    ) -> list[ExclusionDecision]:
        decisions: list[ExclusionDecision] = []

        if opportunity.company_id and candidate_id:
            contact = await self.session.scalar(
                select(ContactHistory).where(
                    ContactHistory.company_id == opportunity.company_id,
                    ContactHistory.candidate_id == candidate_id,
                )
            )
            if contact and contact.status in SUPPRESSING_STATUSES:
                decisions.append(
                    ExclusionDecision(
                        opportunity_id=opportunity.id,
                        reason_code="company_contacted",
                        reason_detail=(
                            f"Company already in state '{contact.status.value}'. "
                            "Suppressed to avoid duplicate outreach."
                        ),
                    )
                )

        if opportunity.deadline and opportunity.deadline < date.today():
            decisions.append(
                ExclusionDecision(
                    opportunity_id=opportunity.id,
                    reason_code="deadline_passed",
                    reason_detail=f"Deadline {opportunity.deadline.isoformat()} has passed.",
                )
            )

        # Clear prior decisions then re-apply
        existing = (
            await self.session.scalars(
                select(ExclusionDecision).where(
                    ExclusionDecision.opportunity_id == opportunity.id
                )
            )
        ).all()
        for row in existing:
            await self.session.delete(row)

        if decisions:
            for d in decisions:
                self.session.add(d)
            opportunity.status = OpportunityStatus.suppressed
        elif opportunity.status == OpportunityStatus.suppressed:
            opportunity.status = OpportunityStatus.new

        await self.session.flush()
        return decisions

    async def reevaluate_for_contact_change(
        self, company_id: UUID, candidate_id: UUID
    ) -> int:
        """Re-run exclusion on all opportunities for this company; returns count changed."""
        opps = (
            await self.session.scalars(
                select(Opportunity)
                .options(selectinload(Opportunity.exclusion_decisions))
                .where(Opportunity.company_id == company_id)
            )
        ).all()
        changed = 0
        for opp in opps:
            before = opp.status
            await self.evaluate_opportunity(opp, candidate_id=candidate_id)
            if opp.status != before:
                changed += 1
        return changed

    def deadline_boost(self, opportunity: Opportunity) -> float:
        """Higher boost when deadline is soon (within radar window)."""
        if not opportunity.deadline:
            return 0.0
        days = (opportunity.deadline - date.today()).days
        window = self.settings.deadline_radar_days
        if days < 0:
            return -1.0
        if days > window:
            return 0.0
        return max(0.0, (window - days) / window)
