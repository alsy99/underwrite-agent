"""Case routes: CRUD + spreads + memo + export."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import (
    RequireMutate,
    RequireRead,
    resolve_tenant,
)
from packages.auth import Principal
from packages.config import get_settings
from packages.db.models import CaseRecord, MemoRecord, SpreadRecord
from packages.db.session import get_session
from packages.memo import build_memo_context, context_hash, render_memo
from packages.schemas.audit import AuditEvent
from packages.schemas.case import (
    CaseFile,
    CaseListItem,
    CaseResponse,
    CaseStatus,
    LoanVertical,
    VarianceFinding,
)
from packages.spreading import compute_variances, parse_tabular, stated_from_metadata

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
    principal: Principal = Depends(RequireMutate),
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

    return CaseResponse(
        case_id=case_id,
        status=CaseStatus.QUEUED,
        vertical=vert,
        tenant_id=tid,
        created_at=case.created_at or datetime.now(timezone.utc),
    )


@router.get("", response_model=list[CaseListItem])
async def list_cases(
    tenant_id: str = "default",
    limit: int = 50,
    principal: Principal = Depends(RequireRead),
    session: AsyncSession = Depends(get_session),
):
    tid = resolve_tenant(principal, tenant_id)
    result = await session.execute(
        select(CaseRecord)
        .where(CaseRecord.tenant_id == tid)
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
    principal: Principal = Depends(RequireRead),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(CaseRecord).where(CaseRecord.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
    if principal.auth_method != "api_key" and case.tenant_id != principal.tenant_id:
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
    principal: Principal = Depends(RequireRead),
    session: AsyncSession = Depends(get_session),
):
    from packages.audit.logger import AuditLogger

    result = await session.execute(select(CaseRecord).where(CaseRecord.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
    if principal.auth_method != "api_key" and case.tenant_id != principal.tenant_id:
        raise HTTPException(404, "Case not found")
    audit = AuditLogger(session, case_id, tenant_id=case.tenant_id)
    return await audit.list_events()


class SpreadResponse(BaseModel):
    id: str
    case_id: str
    source_filename: str
    payload: dict
    variances: list[VarianceFinding]
    created_at: datetime


@router.post("/{case_id}/spreads", response_model=SpreadResponse, status_code=201)
async def upload_spread(
    case_id: str,
    file: UploadFile = File(...),
    principal: Principal = Depends(RequireMutate),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(CaseRecord).where(CaseRecord.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
    if principal.auth_method != "api_key" and case.tenant_id != principal.tenant_id:
        raise HTTPException(404, "Case not found")

    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    filename = file.filename or "spread.csv"
    try:
        payload = parse_tabular(filename, data)
    except Exception as exc:
        raise HTTPException(400, f"Failed to parse spread: {exc}") from exc
    if not payload:
        raise HTTPException(400, "No recognizable metrics in spread file")

    stated = stated_from_metadata(case.metadata_json or {})
    variances = compute_variances(payload, stated, case.vertical)
    record = SpreadRecord(
        case_id=case.id,
        tenant_id=case.tenant_id,
        source_filename=filename,
        payload_json=payload,
        variances_json=[v.model_dump(mode="json") for v in variances],
    )
    session.add(record)

    # Merge into case file if present
    if case.case_file_json:
        cf = CaseFile.model_validate(case.case_file_json)
        cf.spreads_summary = variances
        for v in variances:
            if v.severity in ("high", "medium"):
                cf.open_questions.append(f"Reconcile spread variance: {v.summary}")
        cf.open_questions = list(dict.fromkeys(cf.open_questions))
        case.case_file_json = cf.model_dump(mode="json")

    await session.commit()

    if any(v.severity == "high" for v in variances):
        from packages.los import EVENT_SPREAD_VARIANCE_HIGH, emit_and_deliver

        await emit_and_deliver(
            session,
            tenant_id=case.tenant_id,
            event_type=EVENT_SPREAD_VARIANCE_HIGH,
            payload={"case_id": case.id, "variances": [v.model_dump(mode="json") for v in variances]},
        )

    return SpreadResponse(
        id=record.id,
        case_id=case.id,
        source_filename=filename,
        payload=payload,
        variances=variances,
        created_at=record.created_at or datetime.now(timezone.utc),
    )


@router.get("/{case_id}/spreads", response_model=SpreadResponse | None)
async def get_latest_spread(
    case_id: str,
    principal: Principal = Depends(RequireRead),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(CaseRecord).where(CaseRecord.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
    if principal.auth_method != "api_key" and case.tenant_id != principal.tenant_id:
        raise HTTPException(404, "Case not found")
    spread_result = await session.execute(
        select(SpreadRecord)
        .where(SpreadRecord.case_id == case_id)
        .order_by(SpreadRecord.created_at.desc())
        .limit(1)
    )
    record = spread_result.scalar_one_or_none()
    if not record:
        return None
    return SpreadResponse(
        id=record.id,
        case_id=record.case_id,
        source_filename=record.source_filename,
        payload=record.payload_json,
        variances=[VarianceFinding.model_validate(v) for v in (record.variances_json or [])],
        created_at=record.created_at,
    )


class MemoResponse(BaseModel):
    case_id: str
    version: int
    format: str
    body: str
    context_hash: str
    created_by: str
    created_at: datetime


@router.post("/{case_id}/memo", response_model=MemoResponse, status_code=201)
async def generate_memo(
    case_id: str,
    principal: Principal = Depends(RequireMutate),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(CaseRecord).where(CaseRecord.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
    if principal.auth_method != "api_key" and case.tenant_id != principal.tenant_id:
        raise HTTPException(404, "Case not found")
    if not case.case_file_json:
        raise HTTPException(400, "Case file not ready — wait for investigation to complete")

    cf = CaseFile.model_validate(case.case_file_json)
    spread_result = await session.execute(
        select(SpreadRecord)
        .where(SpreadRecord.case_id == case_id)
        .order_by(SpreadRecord.created_at.desc())
        .limit(1)
    )
    spread_row = spread_result.scalar_one_or_none()
    variances = [
        VarianceFinding.model_validate(v) for v in (spread_row.variances_json if spread_row else [])
    ] or list(cf.spreads_summary)

    ctx = build_memo_context(
        case_id=case.id,
        vertical=case.vertical,
        tenant_id=case.tenant_id,
        metadata=case.metadata_json or {},
        case_file=cf,
        spread=spread_row.payload_json if spread_row else {},
        variances=variances,
    )
    body = render_memo(case.vertical, ctx)
    chash = context_hash(ctx)

    ver_result = await session.execute(
        select(MemoRecord)
        .where(MemoRecord.case_id == case_id)
        .order_by(MemoRecord.version.desc())
        .limit(1)
    )
    prev = ver_result.scalar_one_or_none()
    version = (prev.version + 1) if prev else 1
    memo = MemoRecord(
        case_id=case.id,
        tenant_id=case.tenant_id,
        version=version,
        format="markdown",
        body=body,
        context_hash=chash,
        created_by=principal.actor,
    )
    session.add(memo)
    cf.memo_version = version
    cf.spreads_summary = variances
    case.case_file_json = cf.model_dump(mode="json")
    await session.commit()

    from packages.los import EVENT_MEMO_READY, emit_and_deliver

    await emit_and_deliver(
        session,
        tenant_id=case.tenant_id,
        event_type=EVENT_MEMO_READY,
        payload={"case_id": case.id, "memo_version": version},
    )

    return MemoResponse(
        case_id=case.id,
        version=version,
        format="markdown",
        body=body,
        context_hash=chash,
        created_by=principal.actor,
        created_at=memo.created_at or datetime.now(timezone.utc),
    )


@router.get("/{case_id}/memo", response_model=MemoResponse)
async def get_latest_memo(
    case_id: str,
    principal: Principal = Depends(RequireRead),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(CaseRecord).where(CaseRecord.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
    if principal.auth_method != "api_key" and case.tenant_id != principal.tenant_id:
        raise HTTPException(404, "Case not found")
    memo_result = await session.execute(
        select(MemoRecord)
        .where(MemoRecord.case_id == case_id)
        .order_by(MemoRecord.version.desc())
        .limit(1)
    )
    memo = memo_result.scalar_one_or_none()
    if not memo:
        raise HTTPException(404, "No memo generated yet")
    return MemoResponse(
        case_id=memo.case_id,
        version=memo.version,
        format=memo.format,
        body=memo.body,
        context_hash=memo.context_hash,
        created_by=memo.created_by,
        created_at=memo.created_at,
    )


@router.get("/{case_id}/memo/{version}", response_model=MemoResponse)
async def get_memo_version(
    case_id: str,
    version: int,
    principal: Principal = Depends(RequireRead),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(CaseRecord).where(CaseRecord.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
    if principal.auth_method != "api_key" and case.tenant_id != principal.tenant_id:
        raise HTTPException(404, "Case not found")
    memo_result = await session.execute(
        select(MemoRecord).where(MemoRecord.case_id == case_id, MemoRecord.version == version)
    )
    memo = memo_result.scalar_one_or_none()
    if not memo:
        raise HTTPException(404, "Memo version not found")
    return MemoResponse(
        case_id=memo.case_id,
        version=memo.version,
        format=memo.format,
        body=memo.body,
        context_hash=memo.context_hash,
        created_by=memo.created_by,
        created_at=memo.created_at,
    )


@router.get("/{case_id}/export")
async def export_case(
    case_id: str,
    principal: Principal = Depends(RequireRead),
    session: AsyncSession = Depends(get_session),
):
    from packages.los import build_case_export

    result = await session.execute(select(CaseRecord).where(CaseRecord.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")
    if principal.auth_method != "api_key" and case.tenant_id != principal.tenant_id:
        raise HTTPException(404, "Case not found")
    return await build_case_export(session, case)
