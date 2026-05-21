from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import verify_api_key
from packages.db.session import get_session
from packages.policy_rag.service import PolicyRAGService

router = APIRouter(prefix="/v1/tenants", tags=["policies"])


class PolicyResponse(BaseModel):
    id: str
    tenant_id: str
    title: str
    policy_version: str
    effective_date: str


class PolicyTextUpload(BaseModel):
    title: str
    content: str
    policy_version: str = ""
    effective_date: str = ""
    filename: str = "policy.md"


@router.post("/{tenant_id}/policies/json", response_model=PolicyResponse, status_code=201)
async def upload_policy_json(
    tenant_id: str,
    body: PolicyTextUpload,
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
):
    """Upload policy as JSON (Postman-friendly — no multipart file required)."""
    if not body.content.strip():
        raise HTTPException(400, "content must not be empty")
    service = PolicyRAGService(session)
    policy = await service.ingest_policy(
        tenant_id,
        body.title,
        body.filename,
        body.content.encode("utf-8"),
        policy_version=body.policy_version or date.today().isoformat(),
        effective_date=body.effective_date or date.today().isoformat(),
    )
    await session.commit()
    return PolicyResponse(
        id=policy.id,
        tenant_id=policy.tenant_id,
        title=policy.title,
        policy_version=policy.policy_version,
        effective_date=policy.effective_date,
    )


@router.post("/{tenant_id}/policies", response_model=PolicyResponse, status_code=201)
async def upload_policy(
    tenant_id: str,
    title: str = Form(...),
    policy_version: str = Form(default=""),
    effective_date: str = Form(default=""),
    file: UploadFile = File(...),
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    service = PolicyRAGService(session)
    policy = await service.ingest_policy(
        tenant_id,
        title,
        file.filename or "policy.md",
        data,
        policy_version=policy_version or date.today().isoformat(),
        effective_date=effective_date or date.today().isoformat(),
    )
    await session.commit()
    return PolicyResponse(
        id=policy.id,
        tenant_id=policy.tenant_id,
        title=policy.title,
        policy_version=policy.policy_version,
        effective_date=policy.effective_date,
    )


@router.get("/{tenant_id}/policies", response_model=list[PolicyResponse])
async def list_policies(
    tenant_id: str,
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
):
    service = PolicyRAGService(session)
    policies = await service.list_policies(tenant_id)
    return [
        PolicyResponse(
            id=p.id,
            tenant_id=p.tenant_id,
            title=p.title,
            policy_version=p.policy_version,
            effective_date=p.effective_date,
        )
        for p in policies
    ]
