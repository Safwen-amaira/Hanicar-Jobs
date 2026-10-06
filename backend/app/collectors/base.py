"""Opportunity collectors - public APIs and RSS only. No LinkedIn/Indeed scraping."""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode, urljoin, urlparse

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


class JobicyCollector(BaseCollector):
    """Jobicy public API - curated remote roles."""

    name = "jobicy"

    async def collect(self, keywords: list[str], locations: list[str]) -> list[RawOpportunity]:
        results: list[RawOpportunity] = []
        params = {"count": 80}
        if keywords:
            params["tag"] = ",".join(keywords[:4])
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get("https://jobicy.com/api/v2/remote-jobs", params=params)
            r.raise_for_status()
            data = r.json().get("jobs", [])
        kw = [k.lower() for k in keywords]
        for job in data:
            title = job.get("jobTitle") or "Untitled"
            desc = job.get("jobDescription") or ""
            blob = f"{title} {desc} {job.get('jobIndustry','')}".lower()
            if kw and not any(k in blob for k in kw):
                continue
            url = job.get("url")
            company = job.get("companyName") or "Unknown"
            results.append(
                RawOpportunity(
                    title=title,
                    description=desc[:8000],
                    company_name=company,
                    company_domain=_domain_from_url(job.get("companyLogo") or url),
                    source=self.name,
                    source_url=url,
                    location=job.get("jobGeo") or "Remote",
                    remote=True,
                    opportunity_type_hint=_guess_type(title, desc),
                )
            )
        return results[:80]


class TheMuseCollector(BaseCollector):
    """The Muse public jobs API."""

    name = "themuse"

    async def collect(self, keywords: list[str], locations: list[str]) -> list[RawOpportunity]:
        results: list[RawOpportunity] = []
        params: dict[str, Any] = {"page": 1, "descending": "true"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get("https://www.themuse.com/api/public/jobs", params=params)
            r.raise_for_status()
            data = r.json().get("results", [])
        kw = [k.lower() for k in keywords]
        loc = [l.lower() for l in locations]
        for job in data:
            title = job.get("name") or "Untitled"
            desc = job.get("contents") or ""
            company = (job.get("company") or {}).get("name") or "Unknown"
            locations_text = ", ".join((item.get("name") or "") for item in job.get("locations") or [])
            blob = f"{title} {desc} {company}".lower()
            if kw and not any(k in blob for k in kw):
                continue
            if loc and locations_text and not any(l in locations_text.lower() for l in loc):
                continue
            url = job.get("refs", {}).get("landing_page")
            results.append(
                RawOpportunity(
                    title=title,
                    description=desc[:8000],
                    company_name=company,
                    company_domain=_domain_from_url(url),
                    source=self.name,
                    source_url=url,
                    location=locations_text or None,
                    remote="remote" in locations_text.lower() or "remote" in blob,
                    opportunity_type_hint=_guess_type(title, desc),
                )
            )
        return results[:80]


class TanitJobsCollector(BaseCollector):
    """TanitJobs public Tunisia jobs page."""

    name = "tanitjobs"

    async def collect(self, keywords: list[str], locations: list[str]) -> list[RawOpportunity]:
        from bs4 import BeautifulSoup

        query = " ".join(keywords[:4]).strip()
        params = {"listing_type[equal]": "Job"}
        if query:
            params["keywords[all_words]"] = query
        url = "https://www.tanitjobs.com/jobs/"
        if params:
            url = f"{url}?{urlencode(params)}"
        headers = {"User-Agent": "HanicarJobs/0.1 (public jobs discovery)"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        cards = soup.select("[class*=job], article, .listing-item, .media")
        if not cards:
            cards = soup.find_all("a", href=True)
        kw = [k.lower() for k in keywords]
        loc = [l.lower() for l in locations]
        results: list[RawOpportunity] = []
        seen: set[str] = set()
        for card in cards[:120]:
            link = card if getattr(card, "name", "") == "a" else card.find("a", href=True)
            href = link.get("href") if link else None
            absolute = urljoin(url, href) if href else url
            if absolute in seen or not is_safe_public_url(absolute):
                continue
            text = " ".join(card.get_text(" ", strip=True).split())
            if len(text) < 20:
                continue
            title = (link.get_text(" ", strip=True) if link else text[:90]).strip() or "TanitJobs opportunity"
            blob = f"{title} {text}".lower()
            if kw and not any(k in blob for k in kw):
                continue
            if loc and not any(l in blob for l in loc):
                continue
            seen.add(absolute)
            company = "TanitJobs"
            bits = [part.strip(" -|") for part in text.split("  ") if part.strip()]
            if len(bits) > 1 and len(bits[0]) < 80:
                company = bits[0]
            results.append(
                RawOpportunity(
                    title=title[:512],
                    description=text[:8000],
                    company_name=company,
                    company_domain=_domain_from_url(absolute),
                    source=self.name,
                    source_url=absolute,
                    location="Tunisia",
                    remote="remote" in blob or "télétravail" in blob,
                    opportunity_type_hint=_guess_type(title, text),
                    country="TN",
                )
            )
        return results[:80]


class WeWorkRemotelyCollector(BaseCollector):
    """We Work Remotely public programming RSS feed."""

    name = "weworkremotely"

    async def collect(self, keywords: list[str], locations: list[str]) -> list[RawOpportunity]:
        rss = RSSCollector("https://weworkremotely.com/categories/remote-programming-jobs.rss")
        rows = await rss.collect(keywords, locations)
        for row in rows:
            row.source = self.name
            row.remote = True
            row.location = row.location or "Remote"
        return rows


class InternetSearchCollector(BaseCollector):
    """General web search for public job pages, used alongside curated sources."""

    name = "internet"

    async def collect(self, keywords: list[str], locations: list[str]) -> list[RawOpportunity]:
        from bs4 import BeautifulSoup

        terms = " ".join([*keywords[:5], *locations[:3], "job OR careers OR internship OR recruitment"]).strip()
        if not terms:
            return []
        search_url = f"https://html.duckduckgo.com/html/?{urlencode({'q': terms})}"
        headers = {"User-Agent": "HanicarJobs/0.1 (public internet job search)"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
            r = await client.get(search_url)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            links: list[tuple[str, str]] = []
            for a in soup.select("a.result__a, a[href]"):
                href = str(a.get("href") or "")
                text = " ".join(a.get_text(" ", strip=True).split())
                if not href.startswith("http") or not text:
                    continue
                if any(block in href for block in ("linkedin.com", "indeed.com")):
                    continue
                if not any(token in f"{href} {text}".lower() for token in ("job", "career", "recruit", "stage", "intern", "emploi", "offre")):
                    continue
                if is_safe_public_url(href):
                    links.append((href, text))
                if len(links) >= 18:
                    break

            results: list[RawOpportunity] = []
            kw = [k.lower() for k in keywords]
            loc = [l.lower() for l in locations]
            for href, title in links:
                try:
                    page = await client.get(href)
                    page.raise_for_status()
                except Exception:
                    continue
                content_type = page.headers.get("content-type", "")
                if "text/html" not in content_type and "text/plain" not in content_type:
                    continue
                page_soup = BeautifulSoup(page.text[:180000], "lxml")
                for tag in page_soup(["script", "style", "noscript"]):
                    tag.decompose()
                text = " ".join(page_soup.get_text(" ", strip=True).split())[:8000]
                blob = f"{title} {text}".lower()
                if kw and not any(k in blob for k in kw):
                    continue
                if loc and not any(l in blob for l in loc):
                    continue
                results.append(
                    RawOpportunity(
                        title=title[:512],
                        description=text,
                        company_name=_domain_from_url(href) or "Internet",
                        company_domain=_domain_from_url(href),
                        source=self.name,
                        source_url=href,
                        location=", ".join(locations) or None,
                        remote="remote" in blob or "télétravail" in blob,
                        opportunity_type_hint=_guess_type(title, text),
                    )
                )
        return results[:40]


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
    return [
        TanitJobsCollector(),
        RemotiveCollector(),
        ArbeitnowCollector(),
        RemoteOKCollector(),
        JobicyCollector(),
        TheMuseCollector(),
        WeWorkRemotelyCollector(),
        InternetSearchCollector(),
    ]
