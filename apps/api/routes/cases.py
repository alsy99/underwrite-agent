import json
import uuid
from datetime import datetime, timezone

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from apps.api.deps import verify_api_key
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.config import get_settings
from packages.db.models import CaseRecord
from packages.db.session import get_session
from packages.schemas.case import (
    CaseFile,
    CaseListItem,
    CaseResponse,
    CaseStatus,
    LoanVertical,
)
from packages.schemas.audit import AuditEvent

router = APIRouter(prefix="/v1/cases", tags=["cases"])


async def _enqueue_case(case_id: str) -> None:
    import os

    from packages.agent.investigation import InvestigationRunner

    if os.getenv("SYNC_INVESTIGATION", "").lower() in ("1", "true", "yes"):

        async for session in get_session():
            await InvestigationRunner(session, case_id).run()
            break
        return

    settings = get_settings()
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("process_case", case_id)
        await redis.close()
    except Exception:
        async for session in get_session():
            await InvestigationRunner(session, case_id).run()
            break


@router.post("", response_model=CaseResponse, status_code=202)
async def create_case(
    vertical: str = Form(...),
    tenant_id: str = Form(default="default"),
    metadata: str = Form(default="{}"),
    documents: list[UploadFile] = File(default=[]),
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
):
    try:
        vert = LoanVertical(vertical)
    except ValueError as e:
        raise HTTPException(400, f"Invalid vertical: {vertical}") from e

    try:
        meta = json.loads(metadata) if metadata else {}
    except json.JSONDecodeError as e:
        raise HTTPException(400, "metadata must be valid JSON") from e

    case_id = str(uuid.uuid4())
    case = CaseRecord(
        id=case_id,
        tenant_id=tenant_id,
        vertical=vert.value,
        status=CaseStatus.QUEUED.value,
        metadata_json=meta,
    )
    session.add(case)
    await session.flush()

    if documents:
        from packages.documents.pipeline import DocumentPipeline

        pipeline = DocumentPipeline(session, case_id, tenant_id)
        for doc in documents:
            data = await doc.read()
            await pipeline.ingest_file(doc.filename or "document.txt", data)
    await session.commit()

    await _enqueue_case(case_id)

    return CaseResponse(
        case_id=case_id,
        status=CaseStatus.QUEUED,
        vertical=vert,
        tenant_id=tenant_id,
        created_at=case.created_at or datetime.now(timezone.utc),
    )


@router.get("", response_model=list[CaseListItem])
async def list_cases(
    tenant_id: str = "default",
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CaseRecord)
        .where(CaseRecord.tenant_id == tenant_id)
        .order_by(CaseRecord.created_at.desc())
        .limit(min(limit, 200))
    )
    items: list[CaseListItem] = []
    for case in result.scalars().all():
        action = None
        findings_count = 0
        contradictions_count = 0
        if case.case_file_json:
            cf = CaseFile.model_validate(case.case_file_json)
            action = cf.recommended_action
            findings_count = len(cf.findings)
            contradictions_count = len(cf.contradictions)
        items.append(
            CaseListItem(
                case_id=case.id,
                status=CaseStatus(case.status),
                vertical=LoanVertical(case.vertical),
                tenant_id=case.tenant_id,
                created_at=case.created_at,
                completed_at=case.completed_at,
                recommended_action=action,
                findings_count=findings_count,
                contradictions_count=contradictions_count,
            )
        )
    return items


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(CaseRecord).where(CaseRecord.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")

    case_file = None
    if case.case_file_json:
        case_file = CaseFile.model_validate(case.case_file_json)

    return CaseResponse(
        case_id=case.id,
        status=CaseStatus(case.status),
        vertical=LoanVertical(case.vertical),
        tenant_id=case.tenant_id,
        created_at=case.created_at,
        completed_at=case.completed_at,
        case_file=case_file,
        error=case.error,
    )


@router.get("/{case_id}/audit", response_model=list[AuditEvent])
async def get_case_audit(
    case_id: str,
    session: AsyncSession = Depends(get_session),
):
    from packages.audit.logger import AuditLogger

    result = await session.execute(select(CaseRecord).where(CaseRecord.id == case_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Case not found")
    audit = AuditLogger(session, case_id)
    return await audit.list_events()
