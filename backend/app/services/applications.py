"""Application draft generator and explicit user-triggered sender."""

from __future__ import annotations

import base64
import asyncio
import re
import smtplib
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from io import BytesIO
from urllib.parse import urljoin, urlparse
from uuid import UUID

import httpx
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import is_safe_public_url
from app.llm.providers import CachedLLM, is_fallback_text
from app.models import (
    Application,
    ApplicationStatus,
    Candidate,
    CandidateProfile,
    ContactHistory,
    ContactStatus,
    Opportunity,
    OpportunityStatus,
)
from app.services.exclusion import SUPPRESSING_STATUSES


EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.+-])")


@dataclass
class MailAttachment:
    filename: str
    content_type: str
    data: bytes


class ApplicationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def create_draft(
        self,
        opportunity_id: UUID,
        candidate_id: UUID,
        *,
        override_notes: str = "",
        manual_recontact_override: bool = False,
        use_llm: bool = True,
        fetch_full_offer: bool = True,
    ) -> Application:
        opp = await self.session.get(
            Opportunity,
            opportunity_id,
            options=[selectinload(Opportunity.company)],
        )
        candidate = await self.session.get(Candidate, candidate_id)
        if not opp or not candidate:
            raise ValueError("Opportunity or candidate not found")
        if not manual_recontact_override:
            block = await self._company_recontact_block(opp, candidate.id)
            if block:
                raise ValueError(
                    f"Company already contacted/applied for this candidate: {block}. "
                    "Use the manual override only when you intentionally want to recontact."
                )

        company_name = opp.company.canonical_name if opp.company else "Hiring Team"
        profile = await self._candidate_profile(candidate.id)
        skills = ", ".join((profile.skills or [])[:10]) if profile else ""
        evidence = (profile.cv_text or "").strip()[:2500] if profile else ""
        full_offer = await self._full_offer_text(opp) if fetch_full_offer else (opp.description or "")
        contact_block = self._candidate_contact_block(candidate, profile)
        template = (
            f"Subject: Application - {opp.title}\n\n"
            f"Dear {company_name} team,\n\n"
            f"I am applying for the {opp.title} opportunity"
            f"{' (remote)' if opp.remote else ''}.\n\n"
            f"My profile is aligned with the role through practical experience in "
            f"{skills or 'the skills requested in the posting'}.\n\n"
            f"I am particularly interested in contributing to {company_name} because the role "
            f"matches my focus on reliable delivery, clear communication, and measurable impact.\n\n"
            f"I would welcome the chance to discuss how my background can support your team.\n\n"
            f"Best regards,\n{candidate.name}\n{contact_block}\n"
        )

        body = template
        if use_llm:
            llm = CachedLLM(self.session)
            polished = await llm.complete(
                "Write an exceptional, professional, ATS-optimized cover letter and email body. "
                "Read the full job offer carefully and align the candidate's real experience directly with the top requirements.\n"
                "Structure guidance:\n"
                "- Subject line: Clear email subject mentioning position and company\n"
                "- Professional Salutation\n"
                "- Engaging opening stating the role and enthusiasm for the company\n"
                "- 2 concise body paragraphs linking candidate's actual skills/achievements to the job responsibilities\n"
                "- Strong closing paragraph with clear call to action\n"
                "- Professional signature block with contact details\n\n"
                "Strict constraints: Use ONLY facts, skills, and experience present in the candidate CV/evidence. "
                "Do NOT invent credentials, certifications, or metrics. Do not include external job-board links. Keep tone confident, persuasive, and professional.",
                system="You are an expert executive recruiter writing high-converting, truthful cover letters.",
                untrusted_label="JOB_AND_DRAFT",
                untrusted_body=(
                    f"FULL_JOB_OFFER:\n{opp.title}\n{full_offer[:12000]}\n\n"
                    f"CANDIDATE_SKILLS:\n{skills}\n\n"
                    f"CV_EVIDENCE:\n{evidence}\n\n"
                    f"ALLOWED_CONTACT_DETAILS:\n{contact_block}\n\n"
                    f"DRAFT:\n{template}"
                ),
            )
            if not is_fallback_text(polished) and polished.strip():
                body = polished

        override_log = []
        if override_notes:
            override_log.append(
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "notes": override_notes,
                    "action": "create_with_override",
                    "manual_recontact_override": manual_recontact_override,
                }
            )

        app = Application(
            opportunity_id=opportunity_id,
            candidate_id=candidate_id,
            status=ApplicationStatus.draft,
            draft_body=body,
            override_log=override_log,
            follow_up_due_at=datetime.now(timezone.utc)
            + timedelta(days=self.settings.follow_up_days),
        )
        self.session.add(app)
        await self.session.flush()
        return app

    async def compose_email(self, application_id: UUID) -> dict:
        app, candidate, opp = await self._load_bundle(application_id)
        subject, body = self.split_subject(app.draft_body, opp.title)
        discovery = await self.discover_application_contact(application_id, persist=True)
        profile = await self._candidate_profile(candidate.id)
        cv = (profile.preferences or {}).get("cv_attachment") if profile else None
        uploaded_cover = (
            (profile.preferences or {}).get("cover_letter_attachment") if profile else None
        )
        attachments = [
            {
                "filename": uploaded_cover.get("filename", "cover-letter.pdf")
                if uploaded_cover
                else "cover-letter.pdf",
                "kind": "cover_letter",
            }
        ]
        if cv:
            attachments.append({"filename": cv.get("filename", "cv.pdf"), "kind": "cv"})
        recipient = app.contact_email or discovery.get("selected_email", "")
        warnings = []
        if not recipient:
            warnings.append("No apply email was found automatically. Add a recipient before sending.")
        if not body.strip():
            warnings.append("Email body is empty.")
        if not cv:
            warnings.append("No CV attachment is configured on the candidate profile.")
        return {
            "application_id": app.id,
            "to": recipient,
            "subject": subject,
            "body": body,
            "suggested_attachments": attachments,
            "warnings": warnings,
            "ready": not warnings,
        }

    async def send_email(
        self,
        application_id: UUID,
        *,
        to: str,
        subject: str,
        body: str,
        smtp_settings: dict | None = None,
        attach_cv: bool = True,
        attach_cover_letter: bool = True,
        extra_attachments: list[dict] | None = None,
        manual_recontact_override: bool = False,
        human_verified: bool = False,
    ) -> dict:
        app, candidate, opp = await self._load_bundle(application_id)
        if not human_verified:
            return {
                "sent": False,
                "status": "needs_human_review",
                "detail": "Sending is blocked until a human verifies this package.",
                "attachments": [],
            }
        if not manual_recontact_override:
            block = await self._company_recontact_block(opp, candidate.id, current_application_id=app.id)
            if block:
                return {
                    "sent": False,
                    "status": "duplicate_company",
                    "detail": (
                        f"Skipped because this company was already contacted/applied: {block}. "
                        "Use manual override only when you intentionally want to recontact."
                    ),
                    "attachments": [],
                }
        smtp = self._smtp_settings(smtp_settings or {})
        missing = [k for k in ("host", "username", "password", "from_email") if not smtp.get(k)]
        if missing:
            return {
                "sent": False,
                "status": "config_required",
                "detail": f"Missing SMTP settings: {', '.join(missing)}",
                "attachments": [],
            }

        attachments: list[MailAttachment] = []
        if attach_cover_letter:
            profile = await self._candidate_profile(candidate.id)
            uploaded_cover = (
                (profile.preferences or {}).get("cover_letter_attachment") if profile else None
            )
            if uploaded_cover and uploaded_cover.get("data_base64"):
                attachments.append(
                    MailAttachment(
                        filename=uploaded_cover.get("filename") or f"cover-letter-{app.id}.pdf",
                        content_type="application/pdf",
                        data=base64.b64decode(uploaded_cover["data_base64"]),
                    )
                )
            else:
                attachments.append(
                    MailAttachment(
                        filename=f"cover-letter-{app.id}.pdf",
                        content_type="application/pdf",
                        data=self.cover_letter_pdf_bytes(app, candidate, opp, body),
                    )
                )
        if attach_cv:
            profile = await self._candidate_profile(candidate.id)
            cv = (profile.preferences or {}).get("cv_attachment") if profile else None
            if cv and cv.get("data_base64"):
                attachments.append(
                    MailAttachment(
                        filename=cv.get("filename") or "cv.pdf",
                        content_type=cv.get("content_type") or "application/pdf",
                        data=base64.b64decode(cv["data_base64"]),
                    )
                )
        for item in extra_attachments or []:
            attachments.append(
                MailAttachment(
                    filename=item.get("filename", "attachment.bin"),
                    content_type=item.get("content_type", "application/octet-stream"),
                    data=base64.b64decode(item.get("data_base64", "")),
                )
            )

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{smtp.get('from_name') or self.settings.smtp_from_name} <{smtp['from_email']}>"
        msg["To"] = to
        msg.set_content(body)
        for attachment in attachments:
            maintype, _, subtype = attachment.content_type.partition("/")
            msg.add_attachment(
                attachment.data,
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=attachment.filename,
            )

        with smtplib.SMTP(smtp["host"], int(smtp.get("port") or 587), timeout=30) as server:
            if smtp.get("use_tls", True):
                server.starttls()
            server.login(smtp["username"], smtp["password"])
            server.send_message(msg)

        log = list(app.override_log or [])
        log.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "action": "email_sent",
                "to": to,
                "attachments": [a.filename for a in attachments],
                "manual_recontact_override": manual_recontact_override,
                "human_verified": human_verified,
            }
        )
        app.override_log = log
        app.status = ApplicationStatus.sent
        app.contact_email = to
        app.applied_at = app.applied_at or datetime.now(timezone.utc)
        await self._record_company_contact(opp, candidate.id, ContactStatus.applied, f"Application email sent to {to}")
        await self.session.flush()
        return {
            "sent": True,
            "status": "sent",
            "detail": "Email sent after human verification.",
            "attachments": [a.filename for a in attachments],
        }

    async def _status_filters(self, statuses: list[str], fallback: list[ApplicationStatus]) -> list[ApplicationStatus]:
        status_values = []
        for status in statuses:
            try:
                status_values.append(ApplicationStatus(status))
            except ValueError:
                continue
        return status_values or fallback

    async def _preview_application(self, app: Application, *, persist_contact: bool = False) -> dict:
        app, candidate, opp = await self._load_bundle(app.id)
        discovery = await self.discover_application_contact(app.id, persist=persist_contact)
        app, candidate, opp = await self._load_bundle(app.id)
        subject, body = self.split_subject(app.draft_body, opp.title)
        company_name = opp.company.canonical_name if opp.company else ""
        to = app.contact_email or discovery.get("selected_email", "")
        warnings: list[str] = []
        if not to:
            warnings.append("No apply email was found automatically.")
        if not (body or "").strip():
            warnings.append("Email body is empty.")
        block = await self._company_recontact_block(opp, candidate.id, current_application_id=app.id)
        if block:
            warnings.append(f"Company already contacted: {block}")
        return {
            "application_id": str(app.id),
            "opportunity_title": opp.title,
            "company_name": company_name,
            "source": opp.source,
            "status": app.status.value,
            "to": to,
            "subject": subject,
            "warnings": warnings,
            "ready": not warnings,
            "detail": "Ready for human review." if not warnings else warnings[0],
        }

    async def prepare_batch(
        self,
        *,
        max_to_prepare: int,
        statuses: list[str],
        persist_contacts: bool = True,
        polish_with_llm: bool = True,
    ) -> dict:
        status_values = await self._status_filters(
            statuses, [ApplicationStatus.draft, ApplicationStatus.prepared, ApplicationStatus.queued]
        )
        rows = (
            await self.session.scalars(
                select(Application)
                .where(Application.status.in_(status_values))
                .order_by(Application.updated_at.asc())
                .limit(max_to_prepare)
            )
        ).all()
        results: list[dict] = []
        queued = 0
        needs_review = 0
        skipped = 0
        for app in rows:
            try:
                if polish_with_llm:
                    try:
                        await self.regenerate_draft(app.id, instructions="Polish for a human review queue.", tone="concise")
                    except Exception:
                        pass
                preview = await self._preview_application(app, persist_contact=persist_contacts)
                loaded, _, _ = await self._load_bundle(app.id)
                log = list(loaded.override_log or [])
                if preview["ready"]:
                    loaded.status = ApplicationStatus.queued
                    queued += 1
                    preview["status"] = ApplicationStatus.queued.value
                    log.append(
                        {
                            "at": datetime.now(timezone.utc).isoformat(),
                            "action": "queued_for_human_review",
                            "to": preview.get("to"),
                        }
                    )
                elif "Company already contacted" in preview["detail"]:
                    skipped += 1
                    preview["status"] = "skipped"
                else:
                    loaded.status = ApplicationStatus.prepared
                    needs_review += 1
                    preview["status"] = ApplicationStatus.prepared.value
                    log.append(
                        {
                            "at": datetime.now(timezone.utc).isoformat(),
                            "action": "prepared_needs_human_check",
                            "warnings": preview.get("warnings"),
                        }
                    )
                loaded.override_log = log
                if persist_contacts and preview.get("to") and not loaded.contact_email:
                    loaded.contact_email = str(preview["to"])
                await self.session.flush()
                results.append(preview)
            except Exception as exc:
                skipped += 1
                results.append({"application_id": str(app.id), "status": "failed", "detail": str(exc), "ready": False})
        return {
            "attempted": len(rows),
            "queued": queued,
            "needs_review": needs_review,
            "skipped": skipped,
            "results": results,
        }

    async def batch_send(
        self,
        *,
        max_to_send: int,
        delay_seconds: float,
        statuses: list[str],
        smtp_settings: dict | None = None,
        attach_cv: bool = True,
        attach_cover_letter: bool = True,
        dry_run: bool = True,
        manual_recontact_override: bool = False,
        human_verified_ids: list[UUID] | None = None,
    ) -> dict:
        status_values = await self._status_filters(
            statuses, [ApplicationStatus.prepared, ApplicationStatus.queued]
        )
        verified = {str(item) for item in (human_verified_ids or [])}
        if not dry_run and not verified:
            raise ValueError(
                "Live batch send is blocked until each package is human-verified. "
                "Use dry run, prepare-batch, then Review & Send."
            )

        rows = (
            await self.session.scalars(
                select(Application)
                .where(Application.status.in_(status_values))
                .order_by(Application.updated_at.asc())
                .limit(max_to_send)
            )
        ).all()
        results: list[dict] = []
        sent = 0
        skipped = 0
        attempted = 0
        for index, app in enumerate(rows):
            attempted += 1
            try:
                preview = await self._preview_application(app, persist_contact=False)
                if not dry_run and str(app.id) not in verified:
                    skipped += 1
                    results.append({**preview, "status": "needs_human_review", "detail": "Not human-verified."})
                    continue
                if not preview.get("to"):
                    skipped += 1
                    results.append({**preview, "status": "skipped"})
                    continue
                if preview.get("warnings") and any("already contacted" in w.lower() for w in preview["warnings"]) and not manual_recontact_override:
                    skipped += 1
                    results.append({**preview, "status": "duplicate_company"})
                    continue
                if dry_run:
                    results.append({**preview, "status": "ready" if preview["ready"] else "needs_check"})
                    continue
                email = await self.compose_email(app.id)
                result = await self.send_email(
                    app.id,
                    to=str(preview["to"]),
                    subject=email["subject"],
                    body=email["body"],
                    smtp_settings=smtp_settings,
                    attach_cv=attach_cv,
                    attach_cover_letter=attach_cover_letter,
                    manual_recontact_override=manual_recontact_override,
                    human_verified=True,
                )
                if result.get("sent"):
                    sent += 1
                else:
                    skipped += 1
                results.append({**preview, **result})
                if index < len(rows) - 1 and delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
            except Exception as exc:
                skipped += 1
                results.append({"application_id": str(app.id), "status": "failed", "detail": str(exc), "ready": False})
        return {"attempted": attempted, "sent": sent, "skipped": skipped, "dry_run": dry_run, "results": results}

    async def discover_application_contact(self, application_id: UUID, *, persist: bool = False) -> dict:
        app, _, opp = await self._load_bundle(application_id)
        emails: list[str] = []
        apply_urls: list[str] = []
        for text in [opp.description or "", app.notes or ""]:
            emails.extend(EMAIL_RE.findall(text))
        if opp.source_url:
            apply_urls.append(opp.source_url)
            page = await self._fetch_page(opp.source_url)
            if page:
                soup = BeautifulSoup(page, "lxml")
                visible = soup.get_text(" ", strip=True)
                emails.extend(EMAIL_RE.findall(visible))
                for a in soup.find_all("a", href=True):
                    href = str(a.get("href") or "").strip()
                    label = a.get_text(" ", strip=True).lower()
                    if href.startswith("mailto:"):
                        emails.extend(EMAIL_RE.findall(href))
                    if any(token in f"{href} {label}".lower() for token in ("apply", "postul", "candid", "career", "recruit")):
                        absolute = urljoin(opp.source_url, href)
                        if is_safe_public_url(absolute):
                            apply_urls.append(absolute)
        clean_emails = list(dict.fromkeys(e.strip(".,;:()[]<>").lower() for e in emails if "example." not in e.lower()))
        clean_urls = list(dict.fromkeys(apply_urls))
        selected = app.contact_email or (clean_emails[0] if clean_emails else "")
        if persist and selected and not app.contact_email:
            app.contact_email = selected
            log = list(app.override_log or [])
            log.append({"at": datetime.now(timezone.utc).isoformat(), "action": "contact_discovered", "email": selected})
            app.override_log = log
            await self.session.flush()
        return {
            "application_id": app.id,
            "emails": clean_emails[:12],
            "apply_urls": clean_urls[:8],
            "selected_email": selected,
            "note": "Email and apply links were extracted from the opportunity text/page when available.",
        }

    async def update_status(
        self, application_id: UUID, status: str | None, override_notes: str = "", **fields: object
    ) -> Application:
        app = await self.session.get(Application, application_id)
        if not app:
            raise ValueError("Application not found")
        log = list(app.override_log or [])
        entry = {"at": datetime.now(timezone.utc).isoformat(), "notes": override_notes}
        if status:
            # Never auto-mark as sent without explicit user action - status update is the user action.
            try:
                new_status = ApplicationStatus(status)
            except ValueError as exc:
                raise ValueError(f"Invalid status: {status}") from exc
            entry.update({"from": app.status.value, "to": new_status.value, "action": "status_update"})
            app.status = new_status
            if new_status in {ApplicationStatus.applied, ApplicationStatus.sent} and not app.applied_at:
                app.applied_at = datetime.now(timezone.utc)
        for key, value in fields.items():
            if value is not None and hasattr(app, key):
                setattr(app, key, value)
        if len(entry) > 2 or override_notes:
            log.append(entry)
        app.override_log = log
        await self.session.flush()
        return app

    async def regenerate_draft(
        self,
        application_id: UUID,
        *,
        instructions: str = "",
        tone: str = "concise",
        include_email_subject: bool = True,
    ) -> Application:
        app, candidate, opp = await self._load_bundle(application_id)
        profile = await self._candidate_profile(candidate.id)
        skills = ", ".join((profile.skills or [])[:16]) if profile else ""
        evidence = (profile.cv_text or "").strip()[:2500] if profile else ""
        full_offer = await self._full_offer_text(opp)
        contact_block = self._candidate_contact_block(candidate, profile)
        subject_rule = "Start with a Subject: line." if include_email_subject else "Do not include a Subject: line."
        llm = CachedLLM(self.session)
        draft = await llm.complete(
            "Write an exceptional, professional, ATS-optimized cover letter for this job application. "
            f"Tone: {tone}. {subject_rule}\n"
            "Structure:\n"
            "- Professional Salutation (e.g. Dear Hiring Team / Hiring Manager)\n"
            "- Strong opening paragraph connecting candidate background to the specific job role\n"
            "- 2 focused body paragraphs highlighting matching skills and achievements from the CV\n"
            "- Professional closing with clear call to action\n"
            "- Complete signature block with allowed contact details\n\n"
            "Strict constraints: Base every claim strictly on the candidate CV evidence. Do NOT invent skills, employers, or metrics. "
            "Do not include external job-board URLs.",
            system="You are an expert executive career advisor crafting compelling, ATS-friendly cover letters.",
            untrusted_label="APPLICATION_CONTEXT",
            untrusted_body=(
                f"CANDIDATE:\n{candidate.name}\n\n"
                f"ALLOWED_CONTACT_DETAILS:\n{contact_block}\n\n"
                f"FULL_JOB_OFFER:\n{opp.title}\n{full_offer[:12000]}\n\n"
                f"KNOWN_SKILLS:\n{skills}\n\nCV_EVIDENCE:\n{evidence}\n\n"
                f"CURRENT_DRAFT:\n{app.draft_body[:4000]}\n\nUSER_INSTRUCTIONS:\n{instructions[:1200]}"
            ),
        )
        if is_fallback_text(draft) or not draft.strip():
            draft = app.draft_body
        log = list(app.override_log or [])
        log.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "action": "llm_regenerate",
                "tone": tone,
                "instructions": instructions[:500],
            }
        )
        app.draft_body = draft
        app.status = ApplicationStatus.prepared
        app.override_log = log
        await self.session.flush()
        return app

    async def follow_up_draft(self, application: Application, candidate: Candidate, title: str) -> str:
        template = (
            f"Subject: Follow-up - {title}\n\n"
            f"Dear Hiring Team,\n\n"
            f"I wanted to kindly follow up on my application for {title}. "
            f"I remain very interested and am happy to provide any additional information.\n\n"
            f"Best regards,\n{candidate.name}\n"
        )
        llm = CachedLLM(self.session)
        polished = await llm.complete(
            "Rewrite this follow-up email so it is polite, concise, and truthful. Do not invent interviews or new credentials.",
            system="You draft follow-up emails. Never send, never invent facts.",
            untrusted_label="FOLLOW_UP",
            untrusted_body=f"CURRENT_DRAFT:\n{application.draft_body[:2500]}\n\nTEMPLATE:\n{template}",
        )
        if is_fallback_text(polished) or not polished.strip():
            return template
        return polished

    async def auto_queue_matches(
        self,
        *,
        candidate_id: UUID,
        min_score: float,
        max_to_draft: int,
        polish_with_llm: bool = True,
    ) -> dict:
        existing_ids = set(
            await self.session.scalars(
                select(Application.opportunity_id).where(Application.candidate_id == candidate_id)
            )
        )
        rows = (
            await self.session.scalars(
                select(Opportunity)
                .where(
                    Opportunity.status == OpportunityStatus.matched,
                    Opportunity.match_score.is_not(None),
                    Opportunity.match_score >= min_score,
                )
                .order_by(Opportunity.match_score.desc())
                .limit(max(max_to_draft * 3, max_to_draft))
            )
        ).all()
        created: list[Application] = []
        skipped = 0
        for opp in rows:
            if opp.id in existing_ids:
                skipped += 1
                continue
            try:
                app = await self.create_draft(
                    opp.id,
                    candidate_id,
                    override_notes="auto-draft from scored matches; human review still required before send",
                    use_llm=polish_with_llm,
                    fetch_full_offer=False,
                )
                await self.discover_application_contact(app.id, persist=True)
                created.append(app)
                existing_ids.add(opp.id)
                if len(created) >= max_to_draft:
                    break
            except ValueError:
                skipped += 1
        return {
            "created": len(created),
            "skipped": skipped,
            "application_ids": [str(app.id) for app in created],
            "note": "Drafts were queued for human review. Nothing was sent.",
        }

    async def automate_for_human_review(
        self,
        *,
        candidate_id: UUID,
        min_score: float,
        max_to_draft: int,
        polish_with_llm: bool = True,
        prepare: bool = True,
    ) -> dict:
        drafted = await self.auto_queue_matches(
            candidate_id=candidate_id,
            min_score=min_score,
            max_to_draft=max_to_draft,
            polish_with_llm=polish_with_llm,
        )
        prepared = {"queued": 0, "needs_review": 0, "skipped": 0, "results": []}
        if prepare and drafted["created"]:
            prepared = await self.prepare_batch(
                max_to_prepare=max(drafted["created"], 1),
                statuses=["draft"],
                persist_contacts=True,
                polish_with_llm=False,
            )
        return {
            **drafted,
            "queued": prepared.get("queued", 0),
            "needs_review": prepared.get("needs_review", 0),
            "prepare_skipped": prepared.get("skipped", 0),
            "note": "Automation drafted and prepared packages. Nothing was sent. Open Review & Send.",
        }

    def split_subject(self, draft: str, fallback_title: str) -> tuple[str, str]:
        lines = (draft or "").splitlines()
        if lines and lines[0].lower().startswith("subject:"):
            subject = lines[0].split(":", 1)[1].strip()
            body = "\n".join(lines[1:]).strip()
            return subject or f"Application - {fallback_title}", body
        return f"Application - {fallback_title}", draft or ""

    def cover_letter_pdf_bytes(
        self, app: Application, candidate: Candidate, opp: Opportunity, body: str | None = None
    ) -> bytes:
        from reportlab.lib.colors import HexColor

        company = opp.company.canonical_name if opp.company else "Hiring Team"
        subject, default_body = self.split_subject(app.draft_body, opp.title)
        text = body or default_body

        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        left = 54
        right = width - 54

        c.setTitle(f"Cover Letter - {candidate.name} - {opp.title}")
        c.setAuthor(candidate.name)
        c.setSubject(subject)

        primary_color = HexColor("#0F172A")
        secondary_color = HexColor("#334155")
        muted_color = HexColor("#64748B")
        line_color = HexColor("#CBD5E1")

        # Header
        c.setFillColor(primary_color)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(left, height - 54, candidate.name)

        c.setFillColor(secondary_color)
        c.setFont("Helvetica", 9.5)
        c.drawString(left, height - 68, candidate.email)
        c.linkURL(f"mailto:{candidate.email}", (left, height - 72, left + 220, height - 62), relative=0)

        c.setStrokeColor(line_color)
        c.setLineWidth(1)
        c.line(left, height - 78, right, height - 78)

        # Recipient & Date
        y = height - 98
        today_str = datetime.now().strftime("%B %d, %Y")
        c.setFillColor(muted_color)
        c.setFont("Helvetica", 9)
        c.drawString(left, y, today_str)

        y -= 20
        c.setFillColor(primary_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left, y, company)

        y -= 14
        c.setFillColor(secondary_color)
        c.setFont("Helvetica", 10)
        c.drawString(left, y, f"Position: {opp.title}")

        y -= 22
        if subject:
            c.setFillColor(primary_color)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(left, y, subject[:100])
            y -= 18

        # Body Text
        c.setFillColor(secondary_color)
        c.setFont("Helvetica", 10.5)
        line_height = 15

        def draw_wrapped(paragraph: str, current_y: float) -> float:
            clean = " ".join(paragraph.split())
            if not clean:
                return current_y - 8
            lines = textwrap.wrap(clean, width=88) or [""]
            for line in lines:
                if current_y < 54:
                    c.showPage()
                    c.setFillColor(secondary_color)
                    c.setFont("Helvetica", 10.5)
                    current_y = height - 54
                c.drawString(left, current_y, line[:110])
                link_target = self._line_link_target(line)
                if link_target:
                    c.linkURL(
                        link_target,
                        (left, current_y - 2, min(right, left + c.stringWidth(line[:110], "Helvetica", 10.5)), current_y + 11),
                        relative=0,
                    )
                current_y -= line_height
            return current_y - 6

        for raw_line in text.splitlines() or [""]:
            y = draw_wrapped(raw_line, y)

        c.setFillColor(muted_color)
        c.setFont("Helvetica", 8)
        c.drawString(left, 34, f"{candidate.name} — Cover Letter")
        c.drawRightString(right, 34, "ATS-Friendly Format")
        c.showPage()
        c.save()
        return buf.getvalue()

    async def cv_pdf_bytes(self, candidate_id: UUID) -> bytes:
        candidate = await self.session.get(Candidate, candidate_id)
        profile = await self._candidate_profile(candidate_id)
        if not candidate or not profile:
            raise ValueError("Candidate profile not found")
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        left = 54
        right = width - 54
        y = height - 52
        c.setTitle(f"ATS CV - {candidate.name}")
        c.setAuthor(candidate.name)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(left, y, candidate.name[:90])
        y -= 16
        c.setFont("Helvetica", 9)
        c.drawString(left, y, candidate.email[:110])
        y -= 28

        def section(title: str) -> None:
            nonlocal y
            if y < 86:
                c.showPage()
                y = height - 54
            c.setFont("Helvetica-Bold", 11)
            c.drawString(left, y, title)
            y -= 15
            c.setFont("Helvetica", 10)

        def lines(text: str, width_chars: int = 96) -> None:
            nonlocal y
            for paragraph in text.splitlines() or [""]:
                for line in textwrap.wrap(" ".join(paragraph.split()), width=width_chars) or [""]:
                    if y < 54:
                        c.showPage()
                        c.setFont("Helvetica", 10)
                        y = height - 54
                    c.drawString(left, y, line[:118])
                    y -= 13
                if paragraph.strip() == "":
                    y -= 3

        section("Professional Profile")
        lines(profile.cv_text[:7000] or "Add CV text in the profile screen to generate a richer ATS CV.")
        if profile.skills:
            y -= 6
            section("Skills")
            lines(", ".join(str(skill) for skill in profile.skills[:48]))
        c.setFont("Helvetica", 8)
        c.drawString(left, 34, self.settings.copyright[:100])
        c.drawRightString(right, 34, "ATS-friendly plain text CV")
        c.showPage()
        c.save()
        return buf.getvalue()

    async def _load_bundle(self, application_id: UUID) -> tuple[Application, Candidate, Opportunity]:
        app = await self.session.get(Application, application_id)
        if not app:
            raise ValueError("Application not found")
        candidate = await self.session.get(Candidate, app.candidate_id)
        opp = await self.session.get(
            Opportunity,
            app.opportunity_id,
            options=[selectinload(Opportunity.company)],
        )
        if not candidate or not opp:
            raise ValueError("Application is missing candidate or opportunity")
        return app, candidate, opp

    async def _candidate_profile(self, candidate_id: UUID) -> CandidateProfile | None:
        return await self.session.scalar(
            select(CandidateProfile).where(CandidateProfile.candidate_id == candidate_id)
        )

    def _line_link_target(self, line: str) -> str:
        email = EMAIL_RE.search(line)
        if email:
            return f"mailto:{email.group(0)}"
        url = re.search(r"https?://(?:www\.)?(?:linkedin\.com|github\.com)/[^\s)>,]+", line, re.I)
        if url:
            return url.group(0)
        phone = re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", line)
        if phone:
            digits = re.sub(r"[^\d+]", "", phone.group(0))
            if len(re.sub(r"\D", "", digits)) >= 8:
                return f"tel:{digits}"
        return ""

    def _candidate_contact_block(self, candidate: Candidate, profile: CandidateProfile | None) -> str:
        prefs = profile.preferences if profile else {}
        parts = [candidate.email]
        for key in ("phone", "linkedin", "github"):
            value = str((prefs or {}).get(key) or "").strip()
            if value:
                parts.append(value)
        return "\n".join(parts)

    async def _fetch_page(self, url: str) -> str:
        if not is_safe_public_url(url):
            return ""
        headers = {"User-Agent": "HanicarJobs/0.1 (application contact discovery)"}
        try:
            async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type and "text/plain" not in content_type:
                    return ""
                return response.text[:250000]
        except Exception:
            return ""

    async def _full_offer_text(self, opp: Opportunity) -> str:
        parts = [opp.description or ""]
        if opp.source_url:
            page = await self._fetch_page(opp.source_url)
            if page:
                soup = BeautifulSoup(page, "lxml")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                parts.append(soup.get_text("\n", strip=True))
        return "\n\n".join(part for part in parts if part).strip() or opp.description or ""

    async def _company_recontact_block(
        self,
        opp: Opportunity,
        candidate_id: UUID,
        *,
        current_application_id: UUID | None = None,
    ) -> str:
        if not opp.company_id:
            return ""
        contact = await self.session.scalar(
            select(ContactHistory).where(
                ContactHistory.company_id == opp.company_id,
                ContactHistory.candidate_id == candidate_id,
            )
        )
        if contact and contact.status in SUPPRESSING_STATUSES:
            return f"contact history is {contact.status.value}"
        existing = (
            await self.session.scalars(
                select(Application)
                .join(Opportunity, Application.opportunity_id == Opportunity.id)
                .where(
                    Opportunity.company_id == opp.company_id,
                    Application.candidate_id == candidate_id,
                    Application.status.in_([ApplicationStatus.sent, ApplicationStatus.applied, ApplicationStatus.interviewing, ApplicationStatus.offer]),
                )
            )
        ).all()
        for row in existing:
            if current_application_id and row.id == current_application_id:
                continue
            return f"application {row.id} is already {row.status.value}"
        return ""

    async def _record_company_contact(
        self, opp: Opportunity, candidate_id: UUID, status: ContactStatus, notes: str
    ) -> None:
        if not opp.company_id:
            return
        row = await self.session.scalar(
            select(ContactHistory).where(
                ContactHistory.company_id == opp.company_id,
                ContactHistory.candidate_id == candidate_id,
            )
        )
        now = datetime.now(timezone.utc)
        if not row:
            self.session.add(
                ContactHistory(
                    company_id=opp.company_id,
                    candidate_id=candidate_id,
                    status=status,
                    contacted_at=now,
                    notes=notes,
                )
            )
        else:
            row.status = status
            row.contacted_at = row.contacted_at or now
            row.notes = "\n".join(part for part in [row.notes, notes] if part).strip()

    def _smtp_settings(self, body: dict) -> dict:
        return {
            "host": body.get("host") or self.settings.smtp_host,
            "port": body.get("port") or self.settings.smtp_port,
            "username": body.get("username") or self.settings.smtp_username,
            "password": body.get("password") or self.settings.smtp_password,
            "from_email": body.get("from_email") or self.settings.smtp_from_email,
            "from_name": body.get("from_name") or self.settings.smtp_from_name,
            "use_tls": body.get("use_tls", self.settings.smtp_use_tls),
        }
