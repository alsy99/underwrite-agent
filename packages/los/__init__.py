"""LOS-agnostic events, HMAC webhooks, export, and ingest helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import (
    CaseRecord,
    MemoRecord,
    SpreadRecord,
    WebhookDeliveryRecord,
    WebhookEndpointRecord,
)
from packages.schemas.case import CaseFile

logger = logging.getLogger(__name__)

EVENT_CASE_COMPLETED = "case.completed"
EVENT_MEMO_READY = "case.memo_ready"
EVENT_SPREAD_VARIANCE_HIGH = "spread.variance_high"
EVENT_RECOMMENDATION_UPDATED = "recommendation.updated"


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    expected = sign_payload(secret, body)
    return hmac.compare_digest(expected, signature or "")


async def list_endpoints_for_event(
    session: AsyncSession, tenant_id: str, event_type: str
) -> list[WebhookEndpointRecord]:
    result = await session.execute(
        select(WebhookEndpointRecord).where(
            WebhookEndpointRecord.tenant_id == tenant_id,
            WebhookEndpointRecord.active.is_(True),
        )
    )
    endpoints = []
    for ep in result.scalars().all():
        events = ep.events_json or []
        if not events or event_type in events or "*" in events:
            endpoints.append(ep)
    return endpoints


async def enqueue_event(
    session: AsyncSession,
    *,
    tenant_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> list[str]:
    """Create pending delivery rows; return delivery ids."""
    endpoints = await list_endpoints_for_event(session, tenant_id, event_type)
    ids: list[str] = []
    for ep in endpoints:
        delivery = WebhookDeliveryRecord(
            endpoint_id=ep.id,
            tenant_id=tenant_id,
            event_type=event_type,
            payload_json={"event": event_type, "payload": payload},
            status="pending",
            attempts=0,
        )
        session.add(delivery)
        await session.flush()
        ids.append(delivery.id)
    return ids


async def deliver_webhook(session: AsyncSession, delivery_id: str) -> bool:
    result = await session.execute(
        select(WebhookDeliveryRecord).where(WebhookDeliveryRecord.id == delivery_id)
    )
    delivery = result.scalar_one_or_none()
    if not delivery:
        return False
    ep_result = await session.execute(
        select(WebhookEndpointRecord).where(WebhookEndpointRecord.id == delivery.endpoint_id)
    )
    endpoint = ep_result.scalar_one_or_none()
    if not endpoint or not endpoint.active:
        delivery.status = "skipped"
        await session.commit()
        return False

    body = json.dumps(delivery.payload_json, default=str).encode("utf-8")
    sig = sign_payload(endpoint.secret, body)
    delivery.attempts += 1
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                endpoint.url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Underwrite-Signature": sig,
                    "X-Underwrite-Event": delivery.event_type,
                },
            )
        if 200 <= resp.status_code < 300:
            delivery.status = "delivered"
            delivery.delivered_at = datetime.now(timezone.utc)
            delivery.last_error = None
            await session.commit()
            return True
        delivery.status = "failed"
        delivery.last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
    except Exception as exc:
        delivery.status = "failed"
        delivery.last_error = str(exc)
        logger.exception("Webhook delivery %s failed", delivery_id)
    await session.commit()
    return False


async def build_case_export(session: AsyncSession, case: CaseRecord) -> dict[str, Any]:
    spread_result = await session.execute(
        select(SpreadRecord)
        .where(SpreadRecord.case_id == case.id)
        .order_by(SpreadRecord.created_at.desc())
        .limit(1)
    )
    spread = spread_result.scalar_one_or_none()
    memo_result = await session.execute(
        select(MemoRecord)
        .where(MemoRecord.case_id == case.id)
        .order_by(MemoRecord.version.desc())
        .limit(1)
    )
    memo = memo_result.scalar_one_or_none()
    case_file = None
    if case.case_file_json:
        case_file = CaseFile.model_validate(case.case_file_json).model_dump(mode="json")
    return {
        "case_id": case.id,
        "tenant_id": case.tenant_id,
        "vertical": case.vertical,
        "status": case.status,
        "metadata": case.metadata_json or {},
        "case_file": case_file,
        "spread": {
            "id": spread.id,
            "payload": spread.payload_json,
            "variances": spread.variances_json,
            "source_filename": spread.source_filename,
        }
        if spread
        else None,
        "memo": {
            "version": memo.version,
            "format": memo.format,
            "context_hash": memo.context_hash,
            "created_by": memo.created_by,
        }
        if memo
        else None,
    }


async def emit_and_deliver(
    session: AsyncSession,
    *,
    tenant_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> list[str]:
    ids = await enqueue_event(
        session, tenant_id=tenant_id, event_type=event_type, payload=payload
    )
    await session.commit()
    for did in ids:
        await deliver_webhook(session, did)
    return ids
