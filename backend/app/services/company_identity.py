"""Company identity resolution: domain first, normalized name second, embeddings last."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Company, CompanyAlias


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(
        r"\b(sa|sarl|sas|ltd|llc|inc|gmbh|tunisia|tunisie|france|tn|fr|uk|usa|uae)\b",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_domain(domain: Optional[str]) -> Optional[str]:
    if not domain:
        return None
    d = domain.lower().strip()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0]
    d = d.removeprefix("www.")
    return d or None


class CompanyIdentityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve(
        self,
        name: str,
        domain: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Company:
        domain_n = normalize_domain(domain)
        name_n = normalize_name(name)

        if domain_n:
            by_domain = await self.session.scalar(
                select(CompanyAlias)
                .options(selectinload(CompanyAlias.company))
                .where(
                    CompanyAlias.alias == domain_n,
                    CompanyAlias.alias_type == "domain",
                )
            )
            if by_domain:
                company = by_domain.company
                await self._ensure_name_alias(company, name_n, name)
                return company

            by_company_domain = await self.session.scalar(
                select(Company).where(Company.domain == domain_n)
            )
            if by_company_domain:
                await self._ensure_name_alias(by_company_domain, name_n, name)
                return by_company_domain

        by_name = await self.session.scalar(
            select(CompanyAlias)
            .options(selectinload(CompanyAlias.company))
            .where(CompanyAlias.alias == name_n, CompanyAlias.alias_type == "name")
        )
        if by_name:
            company = by_name.company
            if domain_n and not company.domain:
                company.domain = domain_n
                await self._ensure_domain_alias(company, domain_n)
            return company

        # Embeddings last - only if AI embeddings available; for now skip to create.
        company = Company(
            canonical_name=name.strip(),
            domain=domain_n,
            country=(country or "").upper() or None,
        )
        self.session.add(company)
        await self.session.flush()
        await self._ensure_name_alias(company, name_n, name)
        if domain_n:
            await self._ensure_domain_alias(company, domain_n)
        return company

    async def _ensure_name_alias(self, company: Company, name_n: str, raw: str) -> None:
        if not name_n:
            return
        existing = await self.session.scalar(
            select(CompanyAlias).where(
                CompanyAlias.alias == name_n, CompanyAlias.alias_type == "name"
            )
        )
        if existing:
            return
        self.session.add(
            CompanyAlias(company_id=company.id, alias=name_n, alias_type="name")
        )
        # Also store raw lower form if different
        raw_n = normalize_name(raw)
        if raw_n and raw_n != name_n:
            return

    async def _ensure_domain_alias(self, company: Company, domain_n: str) -> None:
        existing = await self.session.scalar(
            select(CompanyAlias).where(
                CompanyAlias.alias == domain_n, CompanyAlias.alias_type == "domain"
            )
        )
        if existing:
            return
        self.session.add(
            CompanyAlias(company_id=company.id, alias=domain_n, alias_type="domain")
        )

    async def get(self, company_id: UUID) -> Optional[Company]:
        return await self.session.get(Company, company_id)
