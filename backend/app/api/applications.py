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
    ApplicationBatchPrepareIn,
    ApplicationBatchPrepareOut,
    ApplicationAutoQueueIn,
    ApplicationAutoQueueOut,
    ApplicationBatchSendIn,
    ApplicationBatchSendOut,
    ApplicationCreate,
    ApplicationContactDiscoveryOut,
    ApplicationEmailComposeOut,
    ApplicationEmailSendIn,
    ApplicationEmailSendOut,
    ApplicationOut,
    ApplicationRegenerateIn,
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
        applied_at=app.applied_at,
        interview_at=app.interview_at,
        decision_at=app.decision_at,
        next_action_at=app.next_action_at,
        contact_name=app.contact_name or "",
        contact_email=app.contact_email or "",
        notes=app.notes or "",
        created_at=app.created_at,
        updated_at=app.updated_at,
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
            body.opportunity_id,
            body.candidate_id,
            override_notes=body.override_notes,
            manual_recontact_override=body.manual_recontact_override,
        )
    except ValueError as exc:
        raise HTTPException(409 if "already contacted" in str(exc) else 404, str(exc)) from exc
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
        app = await svc.update_status(
            application_id,
            body.status,
            body.override_notes,
            follow_up_due_at=body.follow_up_due_at,
            applied_at=body.applied_at,
            interview_at=body.interview_at,
            decision_at=body.decision_at,
            next_action_at=body.next_action_at,
            contact_name=body.contact_name,
            contact_email=body.contact_email,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    opp = await db.get(Opportunity, app.opportunity_id)
    company = await db.get(Company, opp.company_id) if opp and opp.company_id else None
    return _out(app, opp, company)


@router.post("/{application_id}/regenerate", response_model=ApplicationOut)
async def regenerate_application(
    application_id: UUID, body: ApplicationRegenerateIn, db: AsyncSession = Depends(get_db)
):
    svc = ApplicationService(db)
    try:
        app = await svc.regenerate_draft(
            application_id,
            instructions=body.instructions,
            tone=body.tone,
            include_email_subject=body.include_email_subject,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
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
                Application.status.in_(["draft", "prepared", "queued", "sent", "applied", "interviewing"]),
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
    draft = await svc.follow_up_draft(app, candidate, opp.title if opp else "your role")
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


@router.get("/{application_id}/discover-contact", response_model=ApplicationContactDiscoveryOut)
async def discover_contact(application_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = ApplicationService(db)
    try:
        result = await svc.discover_application_contact(application_id, persist=True)
        await db.commit()
        return result
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
            manual_recontact_override=body.manual_recontact_override,
            human_verified=body.human_verified,
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


@router.post("/batch-prepare", response_model=ApplicationBatchPrepareOut)
async def batch_prepare(body: ApplicationBatchPrepareIn, db: AsyncSession = Depends(get_db)):
    svc = ApplicationService(db)
    result = await svc.prepare_batch(
        max_to_prepare=body.max_to_prepare,
        statuses=body.statuses,
        persist_contacts=body.persist_contacts,
        polish_with_llm=body.polish_with_llm,
    )
    await db.commit()
    return ApplicationBatchPrepareOut(**result)


@router.post("/auto-queue", response_model=ApplicationAutoQueueOut)
async def auto_queue(body: ApplicationAutoQueueIn, db: AsyncSession = Depends(get_db)):
    svc = ApplicationService(db)
    result = await svc.automate_for_human_review(
        candidate_id=body.candidate_id,
        min_score=body.min_score,
        max_to_draft=body.max_to_draft,
        polish_with_llm=body.polish_with_llm,
        prepare=True,
    )
    await db.commit()
    return ApplicationAutoQueueOut(**result)


@router.post("/batch-send", response_model=ApplicationBatchSendOut)
async def batch_send(body: ApplicationBatchSendIn, db: AsyncSession = Depends(get_db)):
    svc = ApplicationService(db)
    try:
        result = await svc.batch_send(
            max_to_send=body.max_to_send,
            delay_seconds=body.delay_seconds,
            statuses=body.statuses,
            smtp_settings=body.smtp.model_dump() if body.smtp else None,
            attach_cv=body.attach_cv,
            attach_cover_letter=body.attach_cover_letter,
            dry_run=body.dry_run,
            manual_recontact_override=body.manual_recontact_override,
            human_verified_ids=body.human_verified_ids,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not body.dry_run:
        await db.commit()
    return ApplicationBatchSendOut(**result)


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


@router.get("/{application_id}/cv.pdf")
async def cv_pdf(application_id: UUID, db: AsyncSession = Depends(get_db)):
    app = await db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Not found")
    svc = ApplicationService(db)
    try:
        pdf = await svc.cv_pdf_bytes(app.candidate_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ats-cv-{application_id}.pdf"'},
    )
