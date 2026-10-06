"""Opportunity collectors - public APIs and RSS only. No LinkedIn/Indeed scraping."""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import feedparser
import httpx

from app.core.security import is_safe_public_url


@dataclass
class RawOpportunity:
    title: str
    description: str
    company_name: str
    company_domain: Optional[str] = None
    source: str = ""
    source_url: Optional[str] = None
    location: Optional[str] = None
    remote: bool = False
    opportunity_type_hint: Optional[str] = None
    country: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def content_hash(self) -> str:
        key = f"{self.source}|{self.source_url}|{self.title}|{self.company_name}"
        return hashlib.sha256(key.encode()).hexdigest()


class BaseCollector(ABC):
    name: str = "base"

    @abstractmethod
    async def collect(self, keywords: list[str], locations: list[str]) -> list[RawOpportunity]:
        raise NotImplementedError


def _guess_type(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if re.search(r"\bpfe\b", text) and ("stage" in text or "intern" in text):
        return "PFE_STAGE"
    if re.search(r"\bpfe\b|projet de fin|end of stud", text):
        return "PFE"
    if "summer" in text and "intern" in text:
        return "SUMMER_INTERNSHIP"
    if "intern" in text or "stage" in text:
        return "INTERNSHIP"
    if "graduate" in text or "junior" in text:
        return "JUNIOR" if "junior" in text else "GRADUATE"
    if "freelance" in text or "contract" in text:
        return "FREELANCE" if "freelance" in text else "CONTRACT"
    if "part[- ]?time" in text:
        return "PART_TIME"
    return "FULL_TIME"


def _domain_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url).hostname or ""
        return host.removeprefix("www.") or None
    except Exception:
        return None


class RemotiveCollector(BaseCollector):
    """Official Remotive public API - remote jobs JSON."""

    name = "remotive"

    async def collect(self, keywords: list[str], locations: list[str]) -> list[RawOpportunity]:
        results: list[RawOpportunity] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get("https://remotive.com/api/remote-jobs")
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        kw = [k.lower() for k in keywords] or [""]
        for job in jobs:
            blob = f"{job.get('title','')} {job.get('description','')} {job.get('category','')}".lower()
            if keywords and not any(k in blob for k in kw if k):
                continue
            title = job.get("title") or "Untitled"
            desc = job.get("description") or ""
            company = job.get("company_name") or "Unknown"
            url = job.get("url")
            results.append(
                RawOpportunity(
                    title=title,
                    description=desc[:8000],
                    company_name=company,
                    company_domain=_domain_from_url(job.get("company_logo_url") or url),
                    source=self.name,
                    source_url=url,
                    location=job.get("candidate_required_location") or "Remote",
                    remote=True,
                    opportunity_type_hint=_guess_type(title, desc),
                )
            )
        return results[:80]


class ArbeitnowCollector(BaseCollector):
    """Arbeitnow public job board API."""

    name = "arbeitnow"

    async def collect(self, keywords: list[str], locations: list[str]) -> list[RawOpportunity]:
        results: list[RawOpportunity] = []
        params = {}
        if keywords:
            params["search"] = " ".join(keywords[:3])
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get("https://www.arbeitnow.com/api/job-board-api", params=params)
            r.raise_for_status()
            data = r.json().get("data", [])
        for job in data:
            title = job.get("title") or "Untitled"
            desc = job.get("description") or ""
            company = job.get("company_name") or "Unknown"
            url = job.get("url")
            tags = job.get("tags") or []
            remote = bool(job.get("remote")) or "remote" in [t.lower() for t in tags]
            results.append(
                RawOpportunity(
                    title=title,
                    description=desc[:8000],
                    company_name=company,
                    company_domain=_domain_from_url(url),
                    source=self.name,
                    source_url=url,
                    location=job.get("location") or ("Remote" if remote else None),
                    remote=remote,
                    opportunity_type_hint=_guess_type(title, desc),
                )
            )
        return results[:80]


class RemoteOKCollector(BaseCollector):
    """RemoteOK public JSON API."""

    name = "remoteok"

    async def collect(self, keywords: list[str], locations: list[str]) -> list[RawOpportunity]:
        results: list[RawOpportunity] = []
        headers = {"User-Agent": "HanicarJobs/0.1 (+https://github.com/hanicar/hanicar-jobs)"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            r = await client.get("https://remoteok.com/api")
            r.raise_for_status()
            data = r.json()
        kw = [k.lower() for k in keywords]
        for job in data:
            if not isinstance(job, dict) or "id" not in job:
                continue
            title = job.get("position") or job.get("title") or "Untitled"
            desc = job.get("description") or ""
            company = job.get("company") or "Unknown"
            blob = f"{title} {desc} {' '.join(job.get('tags') or [])}".lower()
            if kw and not any(k in blob for k in kw):
                continue
            url = job.get("url") or job.get("apply_url")
            results.append(
                RawOpportunity(
                    title=title,
                    description=desc[:8000],
                    company_name=company,
                    company_domain=job.get("company_domain") or _domain_from_url(url),
                    source=self.name,
                    source_url=url,
                    location="Remote",
                    remote=True,
                    opportunity_type_hint=_guess_type(title, desc),
                )
            )
        return results[:80]


class ManualURLCollector(BaseCollector):
    """User-pasted public URL - polite fetch of title/description only if safe."""

    name = "manual"

    def __init__(self, urls: list[str] | None = None):
        self.urls = urls or []

    async def collect(self, keywords: list[str], locations: list[str]) -> list[RawOpportunity]:
        from bs4 import BeautifulSoup

        results: list[RawOpportunity] = []
        headers = {"User-Agent": "HanicarJobs/0.1 (polite fetch; user-requested URL)"}
        async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
            for url in self.urls:
                if not is_safe_public_url(url):
                    continue
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    soup = BeautifulSoup(r.text, "lxml")
                    title = (soup.title.string if soup.title else url) or url
                    desc = " ".join(p.get_text(" ", strip=True) for p in soup.find_all("p")[:8])
                    results.append(
                        RawOpportunity(
                            title=title.strip()[:512],
                            description=desc[:8000],
                            company_name=_domain_from_url(url) or "Manual",
                            company_domain=_domain_from_url(url),
                            source=self.name,
                            source_url=url,
                            opportunity_type_hint=_guess_type(title, desc),
                        )
                    )
                except Exception:
                    continue
        return results


class RSSCollector(BaseCollector):
    name = "rss"

    def __init__(self, feed_url: str):
        self.feed_url = feed_url

    async def collect(self, keywords: list[str], locations: list[str]) -> list[RawOpportunity]:
        if not is_safe_public_url(self.feed_url):
            return []
        parsed = feedparser.parse(self.feed_url)
        results: list[RawOpportunity] = []
        for entry in parsed.entries[:50]:
            title = getattr(entry, "title", "Untitled")
            desc = getattr(entry, "summary", "") or getattr(entry, "description", "")
            link = getattr(entry, "link", None)
            results.append(
                RawOpportunity(
                    title=title,
                    description=desc[:8000],
                    company_name=_domain_from_url(link) or "RSS",
                    company_domain=_domain_from_url(link),
                    source=self.name,
                    source_url=link,
                    opportunity_type_hint=_guess_type(title, desc),
                )
            )
        return results


def default_collectors() -> list[BaseCollector]:
    return [RemotiveCollector(), ArbeitnowCollector(), RemoteOKCollector()]
