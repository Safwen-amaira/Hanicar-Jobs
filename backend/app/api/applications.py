from datetime import datetime, timezone
from io import BytesIO
import smtplib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Application, Candidate, Company, Opportunity
from app.schemas import (
    ApplicationCreate,
    ApplicationEmailComposeOut,
    ApplicationEmailSendIn,
    ApplicationEmailSendOut,
    ApplicationOut,
    ApplicationStatusUpdate,
    SmtpSettingsIn,
    SmtpTestOut,
)
from app.services.applications import ApplicationService

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _out(app: Application, opp: Opportunity | None = None, company: Company | None = None) -> ApplicationOut:
    return ApplicationOut(
        id=app.id,
        opportunity_id=app.opportunity_id,
        candidate_id=app.candidate_id,
        status=app.status.value,
        draft_body=app.draft_body,
        override_log=app.override_log or [],
        follow_up_due_at=app.follow_up_due_at,
        created_at=app.created_at,
        opportunity_title=opp.title if opp else None,
        company_name=company.canonical_name if company else None,
        source=opp.source if opp else None,
        source_url=opp.source_url if opp else None,
    )


@router.post("", response_model=ApplicationOut, status_code=201)
async def create_application(body: ApplicationCreate, db: AsyncSession = Depends(get_db)):
    svc = ApplicationService(db)
    try:
        app = await svc.create_draft(
            body.opportunity_id, body.candidate_id, override_notes=body.override_notes
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    opp = await db.get(Opportunity, app.opportunity_id)
    company = await db.get(Company, opp.company_id) if opp and opp.company_id else None
    return _out(app, opp, company)


@router.get("", response_model=list[ApplicationOut])
async def list_applications(
    candidate_id: UUID | None = None, db: AsyncSession = Depends(get_db)
):
    q = (
        select(Application, Opportunity, Company)
        .join(Opportunity, Application.opportunity_id == Opportunity.id)
        .outerjoin(Company, Opportunity.company_id == Company.id)
        .order_by(Application.updated_at.desc())
    )
    if candidate_id:
        q = q.where(Application.candidate_id == candidate_id)
    rows = (await db.execute(q)).all()
    return [_out(app, opp, company) for app, opp, company in rows]


@router.patch("/{application_id}", response_model=ApplicationOut)
async def update_application(
    application_id: UUID, body: ApplicationStatusUpdate, db: AsyncSession = Depends(get_db)
):
    svc = ApplicationService(db)
    try:
        app = await svc.update_status(application_id, body.status, body.override_notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    opp = await db.get(Opportunity, app.opportunity_id)
    company = await db.get(Company, opp.company_id) if opp and opp.company_id else None
    return _out(app, opp, company)


@router.get("/due/follow-ups", response_model=list[ApplicationOut])
async def due_follow_ups(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    rows = (
        await db.execute(
            select(Application, Opportunity, Company)
            .join(Opportunity, Application.opportunity_id == Opportunity.id)
            .outerjoin(Company, Opportunity.company_id == Company.id)
            .where(
                Application.follow_up_due_at.is_not(None),
                Application.follow_up_due_at <= now,
                Application.status.in_(["draft", "queued", "sent"]),
            )
        )
    ).all()
    return [_out(app, opp, company) for app, opp, company in rows]


@router.get("/{application_id}/follow-up")
async def follow_up_draft(application_id: UUID, db: AsyncSession = Depends(get_db)):
    app = await db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Not found")
    candidate = await db.get(Candidate, app.candidate_id)
    opp = await db.get(Opportunity, app.opportunity_id)
    svc = ApplicationService(db)
    draft = svc.follow_up_draft(app, candidate, opp.title if opp else "your role")
    return {
        "application_id": str(app.id),
        "draft": draft,
        "due_at": app.follow_up_due_at,
        "auto_send": False,
        "note": "Follow-ups are drafts only - never auto-sent.",
    }


@router.get("/{application_id}/email", response_model=ApplicationEmailComposeOut)
async def compose_email(application_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = ApplicationService(db)
    try:
        return await svc.compose_email(application_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/smtp/test", response_model=SmtpTestOut)
async def test_smtp(body: SmtpSettingsIn):
    required = {
        "host": body.host,
        "username": body.username,
        "password": body.password,
        "from_email": body.from_email,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        return SmtpTestOut(
            ok=False,
            status="config_required",
            detail=f"Missing SMTP settings: {', '.join(missing)}",
        )
    try:
        with smtplib.SMTP(body.host, int(body.port or 587), timeout=15) as server:
            if body.use_tls:
                server.starttls()
            server.login(body.username, body.password)
    except Exception as exc:
        return SmtpTestOut(ok=False, status="failed", detail=str(exc))
    return SmtpTestOut(
        ok=True,
        status="ready",
        detail="SMTP credentials were accepted. No email was sent.",
    )


@router.post("/{application_id}/send-email", response_model=ApplicationEmailSendOut)
async def send_email(
    application_id: UUID, body: ApplicationEmailSendIn, db: AsyncSession = Depends(get_db)
):
    svc = ApplicationService(db)
    try:
        result = await svc.send_email(
            application_id,
            to=str(body.to),
            subject=body.subject,
            body=body.body,
            smtp_settings=body.smtp.model_dump() if body.smtp else None,
            attach_cv=body.attach_cv,
            attach_cover_letter=body.attach_cover_letter,
            extra_attachments=[a.model_dump() for a in body.extra_attachments],
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        return ApplicationEmailSendOut(
            sent=False,
            status="failed",
            detail=str(exc),
            attachments=[],
        )
    if result["sent"]:
        await db.commit()
    return ApplicationEmailSendOut(**result)


@router.get("/{application_id}/pdf")
async def application_pdf(application_id: UUID, db: AsyncSession = Depends(get_db)):
    app = await db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Not found")
    settings = get_settings()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    c.setTitle("Hanicar Jobs Application Draft")
    c.setAuthor(settings.copyright)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 50, "Hanicar Jobs - Application Draft")
    c.setFont("Helvetica", 9)
    c.drawString(50, height - 70, settings.copyright)
    c.setFont("Helvetica", 11)
    y = height - 110
    for line in app.draft_body.splitlines() or [""]:
        c.drawString(50, y, line[:100])
        y -= 14
        if y < 50:
            c.showPage()
            y = height - 50
    c.showPage()
    c.save()
    return Response(
        buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="hanicar-draft-{application_id}.pdf"'},
    )


@router.get("/{application_id}/cover-letter.pdf")
async def cover_letter_pdf(application_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = ApplicationService(db)
    try:
        app, candidate, opp = await svc._load_bundle(application_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    pdf = svc.cover_letter_pdf_bytes(app, candidate, opp)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="cover-letter-{application_id}.pdf"'
        },
    )

