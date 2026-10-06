"""Application draft generator - never auto-sends."""

from __future__ import annotations

import base64
import smtplib
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from io import BytesIO
from uuid import UUID

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.llm.providers import CachedLLM
from app.models import Application, ApplicationStatus, Candidate, CandidateProfile, Opportunity


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
    ) -> Application:
        opp = await self.session.get(
            Opportunity,
            opportunity_id,
            options=[selectinload(Opportunity.company)],
        )
        candidate = await self.session.get(Candidate, candidate_id)
        if not opp or not candidate:
            raise ValueError("Opportunity or candidate not found")

        company_name = opp.company.canonical_name if opp.company else "Hiring Team"
        profile = await self._candidate_profile(candidate.id)
        skills = ", ".join((profile.skills or [])[:10]) if profile else ""
        evidence = (profile.cv_text or "").strip()[:900] if profile else ""
        source_line = f"Source: {opp.source}{f' ({opp.source_url})' if opp.source_url else ''}"
        template = (
            f"Subject: Application - {opp.title}\n\n"
            f"Dear {company_name} team,\n\n"
            f"I am applying for the {opp.title} opportunity"
            f"{' (remote)' if opp.remote else ''}. {source_line}.\n\n"
            f"My profile is aligned with the role through practical experience in "
            f"{skills or 'the skills requested in the posting'}.\n\n"
            f"I am particularly interested in contributing to {company_name} because the role "
            f"matches my focus on reliable delivery, clear communication, and measurable impact.\n\n"
            f"I would welcome the chance to discuss how my background can support your team.\n\n"
            f"Best regards,\n{candidate.name}\n{candidate.email}\n"
        )

        llm = CachedLLM(self.session)
        polished = await llm.complete(
            "Rewrite this as an ATS-friendly cover letter and email body. "
            "Use simple section-free paragraphs, include role title, company, source, and only evidence present in the CV/profile. "
            "Do not invent skills, employers, degrees, certifications, dates, or metrics. Keep it concise.",
            system="You draft ATS-friendly job applications. Never invent credentials.",
            untrusted_label="JOB_AND_DRAFT",
            untrusted_body=(
                f"JOB:\n{opp.title}\n{opp.description[:3000]}\n\n"
                f"CANDIDATE_SKILLS:\n{skills}\n\n"
                f"CV_EVIDENCE:\n{evidence}\n\n"
                f"DRAFT:\n{template}"
            ),
        )
        # If mock, prefer template as primary body with mock note appended lightly
        body = template if polished.startswith("[MockProvider]") or polished.startswith("[KaggleProvider]") else polished

        override_log = []
        if override_notes:
            override_log.append(
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "notes": override_notes,
                    "action": "create_with_override",
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
        return {
            "application_id": app.id,
            "to": "",
            "subject": subject,
            "body": body,
            "suggested_attachments": attachments,
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
    ) -> dict:
        app, candidate, opp = await self._load_bundle(application_id)
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
            }
        )
        app.override_log = log
        app.status = ApplicationStatus.sent
        await self.session.flush()
        return {
            "sent": True,
            "status": "sent",
            "detail": "Email sent by explicit user action.",
            "attachments": [a.filename for a in attachments],
        }

    async def update_status(
        self, application_id: UUID, status: str, override_notes: str = ""
    ) -> Application:
        app = await self.session.get(Application, application_id)
        if not app:
            raise ValueError("Application not found")
        # Never auto-mark as sent without explicit user action - status update is the user action.
        try:
            new_status = ApplicationStatus(status)
        except ValueError as exc:
            raise ValueError(f"Invalid status: {status}") from exc
        log = list(app.override_log or [])
        log.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "from": app.status.value,
                "to": new_status.value,
                "notes": override_notes,
            }
        )
        app.status = new_status
        app.override_log = log
        await self.session.flush()
        return app

    def follow_up_draft(self, application: Application, candidate: Candidate, title: str) -> str:
        return (
            f"Subject: Follow-up - {title}\n\n"
            f"Dear Hiring Team,\n\n"
            f"I wanted to kindly follow up on my application for {title}. "
            f"I remain very interested and am happy to provide any additional information.\n\n"
            f"Best regards,\n{candidate.name}\n"
        )

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
        company = opp.company.canonical_name if opp.company else "Hiring Team"
        subject, default_body = self.split_subject(app.draft_body, opp.title)
        text = body or default_body
        source = f"Source: {opp.source}{f' - {opp.source_url}' if opp.source_url else ''}"
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        left = 54
        right = width - 54
        line_height = 14
        c.setTitle(f"ATS Cover Letter - {opp.title}")
        c.setAuthor(candidate.name)
        c.setSubject(subject)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(left, height - 50, candidate.name)
        c.setFont("Helvetica", 9)
        c.drawString(left, height - 66, candidate.email)
        c.drawString(left, height - 86, f"{company} - {opp.title}")
        c.drawString(left, height - 100, source[:120])
        c.setFont("Helvetica-Bold", 12)
        c.drawString(left, height - 128, subject[:96])
        c.setFont("Helvetica", 11)
        y = height - 160

        def draw_wrapped(paragraph: str, current_y: float) -> float:
            clean = " ".join(paragraph.split())
            lines = textwrap.wrap(clean, width=92) or [""]
            for line in lines:
                if current_y < 54:
                    c.showPage()
                    c.setFont("Helvetica", 11)
                    current_y = height - 54
                c.drawString(left, current_y, line[:110])
                current_y -= line_height
            return current_y

        for raw_line in text.splitlines() or [""]:
            y = draw_wrapped(raw_line, y)
            if raw_line.strip() == "":
                y -= 4
        c.setFont("Helvetica", 8)
        c.drawString(left, 34, self.settings.copyright[:120])
        c.drawRightString(right, 34, "ATS-friendly plain text layout")
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
