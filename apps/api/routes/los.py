"""LOS webhooks admin + ingest."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import RequireAdmin, RequireMutate, resolve_tenant
from packages.auth import Principal
from packages.db.models import CaseRecord, WebhookDeliveryRecord, WebhookEndpointRecord
from packages.db.session import get_session
from packages.schemas.case import CaseStatus, LoanVertical

router = APIRouter(prefix="/v1/los", tags=["los"])


class WebhookCreate(BaseModel):
    url: str
    secret: str
    events: list[str] = Field(default_factory=lambda: ["*"])
    tenant_id: str = "default"


class WebhookResponse(BaseModel):
    id: str
    tenant_id: str
    url: str
    events: list[str]
    active: bool
    created_at: datetime


class DeliveryResponse(BaseModel):
    id: str
    event_type: str
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime


@router.post("/webhooks", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    body: WebhookCreate,
    principal: Principal = Depends(RequireAdmin),
    session: AsyncSession = Depends(get_session),
):
    tid = resolve_tenant(principal, body.tenant_id)
    ep = WebhookEndpointRecord(
        tenant_id=tid,
        url=body.url,
        secret=body.secret,
        events_json=body.events,
        active=True,
    )
    session.add(ep)
    await session.commit()
    return WebhookResponse(
        id=ep.id,
        tenant_id=ep.tenant_id,
        url=ep.url,
        events=list(ep.events_json or []),
        active=ep.active,
        created_at=ep.created_at or datetime.now(timezone.utc),
    )


@router.get("/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(
    tenant_id: str = "default",
    principal: Principal = Depends(RequireAdmin),
    session: AsyncSession = Depends(get_session),
):
    tid = resolve_tenant(principal, tenant_id)
    result = await session.execute(
        select(WebhookEndpointRecord).where(WebhookEndpointRecord.tenant_id == tid)
    )
    return [
        WebhookResponse(
            id=ep.id,
            tenant_id=ep.tenant_id,
            url=ep.url,
            events=list(ep.events_json or []),
            active=ep.active,
            created_at=ep.created_at,
        )
        for ep in result.scalars().all()
    ]


@router.get("/deliveries", response_model=list[DeliveryResponse])
async def list_deliveries(
    tenant_id: str = "default",
    limit: int = 50,
    principal: Principal = Depends(RequireAdmin),
    session: AsyncSession = Depends(get_session),
):
    tid = resolve_tenant(principal, tenant_id)
    result = await session.execute(
        select(WebhookDeliveryRecord)
        .where(WebhookDeliveryRecord.tenant_id == tid)
        .order_by(WebhookDeliveryRecord.created_at.desc())
        .limit(min(limit, 200))
    )
    return [
        DeliveryResponse(
            id=d.id,
            event_type=d.event_type,
            status=d.status,
            attempts=d.attempts,
            last_error=d.last_error,
            created_at=d.created_at,
        )
        for d in result.scalars().all()
    ]


@router.post("/ingest", status_code=202)
async def los_ingest(
    vertical: str = Form(...),
    tenant_id: str = Form(default="default"),
    metadata: str = Form(default="{}"),
    external_id: str = Form(default=""),
    documents: list[UploadFile] = File(default=[]),
    principal: Principal = Depends(RequireMutate),
    session: AsyncSession = Depends(get_session),
):
    """LOS pushes a package; creates a case like POST /v1/cases."""
    from apps.api.routes.cases import _enqueue_case

    try:
        vert = LoanVertical(vertical)
    except ValueError as e:
        raise HTTPException(400, f"Invalid vertical: {vertical}") from e
    try:
        meta = json.loads(metadata) if metadata else {}
    except json.JSONDecodeError as e:
        raise HTTPException(400, "metadata must be valid JSON") from e
    if external_id:
        meta["los_external_id"] = external_id

    tid = resolve_tenant(principal, tenant_id)
    case_id = str(uuid.uuid4())
    case = CaseRecord(
        id=case_id,
        tenant_id=tid,
        vertical=vert.value,
        status=CaseStatus.QUEUED.value,
        metadata_json=meta,
    )
    session.add(case)
    await session.flush()
    if documents:
        from packages.documents.pipeline import DocumentPipeline

        pipeline = DocumentPipeline(session, case_id, tid)
        for doc in documents:
            data = await doc.read()
            await pipeline.ingest_file(doc.filename or "document.txt", data)
    await session.commit()
    await _enqueue_case(case_id)
    return {"case_id": case_id, "status": "queued", "tenant_id": tid}
