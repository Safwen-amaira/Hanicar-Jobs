"""Matching: keyword/rules first, optional embeddings, optional LLM. Works with AI off."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.models import CandidateProfile, Opportunity, SearchProfile
from app.services.exclusion import ExclusionEngine


@dataclass
class MatchResult:
    score: float
    reasons: list[str] = field(default_factory=list)
    skill_gaps: list[str] = field(default_factory=list)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-ZÀ-ÿ0-9+#.]{2,}", (text or "").lower()))


class MatchingService:
    def __init__(self, exclusion: ExclusionEngine | None = None):
        self.settings = get_settings()
        self.exclusion = exclusion

    def score(
        self,
        opportunity: Opportunity,
        profile: SearchProfile,
        candidate_profile: CandidateProfile | None = None,
    ) -> MatchResult:
        reasons: list[str] = []
        score = 0.0

        blob = f"{opportunity.title} {opportunity.description} {opportunity.location or ''}".lower()
        tokens = _tokenize(blob)

        # Keyword hits
        kw_hits = 0
        for kw in profile.keywords or []:
            k = kw.lower().strip()
            if k and k in blob:
                kw_hits += 1
                reasons.append(f"Keyword match: {kw}")
        if profile.keywords:
            score += 40.0 * (kw_hits / max(len(profile.keywords), 1))
        else:
            score += 10.0

        # Location
        loc_hits = 0
        for loc in profile.locations or []:
            if loc.lower() in blob or (opportunity.remote and loc.lower() in {"remote", "télétravail", "teletravail"}):
                loc_hits += 1
                reasons.append(f"Location match: {loc}")
        if profile.locations:
            score += 20.0 * min(1.0, loc_hits / max(len(profile.locations), 1))
        if opportunity.remote and "REMOTE_ONLY" in (profile.opportunity_type_codes or []):
            score += 10.0
            reasons.append("Remote-friendly and profile includes REMOTE_ONLY")

        # Opportunity type
        # Type filtering is soft: boost if type on profile (exact check done at collect time too)
        score += 10.0

        # Skills evidence vs required (CV gap - never invent)
        skill_gaps: list[str] = []
        cv_skills = {s.lower() for s in (candidate_profile.skills if candidate_profile else [])}
        cv_text = (candidate_profile.cv_text if candidate_profile else "") or ""
        cv_tokens = _tokenize(cv_text) | cv_skills

        required = self._extract_required_skills(opportunity.description)
        evidenced = 0
        for skill in required:
            if skill.lower() in cv_tokens or any(skill.lower() in t for t in cv_tokens):
                evidenced += 1
                reasons.append(f"CV evidences skill: {skill}")
            else:
                skill_gaps.append(skill)
        if required:
            score += 20.0 * (evidenced / len(required))

        # Deadline radar boost
        if self.exclusion:
            boost = self.exclusion.deadline_boost(opportunity)
            if boost > 0:
                score += 10.0 * boost
                reasons.append("Closing soon - deadline radar boost")

        score = max(0.0, min(100.0, score))
        if not reasons:
            reasons.append("Baseline rule score (no strong keyword hits)")

        return MatchResult(score=round(score, 2), reasons=reasons, skill_gaps=skill_gaps)

    def _extract_required_skills(self, description: str) -> list[str]:
        """Heuristic extraction of required skills from JD text. No invention beyond listed terms."""
        known = [
            "python", "java", "javascript", "typescript", "react", "fastapi", "django",
            "docker", "kubernetes", "aws", "azure", "gcp", "linux", "sql", "postgresql",
            "redis", "security", "cybersecurity", "pentest", "siem", "soc", "network",
            "cloud", "terraform", "ansible", "git", "ci/cd", "machine learning", "nlp",
            "golang", "rust", "c++", "nodejs", "vue", "angular",
        ]
        text = (description or "").lower()
        found = [s for s in known if s in text]
        # Also pull "required: x, y" style lists lightly
        m = re.search(r"(?:required|requirements|compétences|exigences)\s*[:：]\s*(.+)", text, re.I)
        if m:
            chunk = m.group(1)[:200]
            for part in re.split(r"[,;/|]", chunk):
                p = part.strip()
                if 2 <= len(p) <= 40 and p not in found:
                    found.append(p)
        return found[:12]
