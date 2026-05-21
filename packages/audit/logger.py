import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import AuditEventRecord
from packages.schemas.audit import AuditEvent
from packages.schemas.case import Citation


class AuditLogger:
    def __init__(self, session: AsyncSession, case_id: str):
        self.session = session
        self.case_id = case_id

    @staticmethod
    def hash_inputs(data: Any) -> str:
        payload = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    async def log(
        self,
        actor: str,
        action: str,
        outputs: dict[str, Any] | None = None,
        inputs: Any = None,
        citations: list[Citation] | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
    ) -> AuditEvent:
        record = AuditEventRecord(
            id=str(uuid.uuid4()),
            case_id=self.case_id,
            timestamp=datetime.now(timezone.utc),
            actor=actor,
            action=action,
            inputs_hash=self.hash_inputs(inputs) if inputs is not None else None,
            outputs_json=outputs or {},
            citations_json=[c.model_dump() for c in (citations or [])],
            model=model,
            prompt_version=prompt_version,
        )
        self.session.add(record)
        await self.session.flush()
        return AuditEvent(
            event_id=record.id,
            case_id=record.case_id,
            timestamp=record.timestamp,
            actor=record.actor,
            action=record.action,
            inputs_hash=record.inputs_hash,
            outputs=record.outputs_json,
            citations=[Citation(**c) for c in record.citations_json],
            model=record.model,
            prompt_version=record.prompt_version,
        )

    async def list_events(self) -> list[AuditEvent]:
        from sqlalchemy import select

        result = await self.session.execute(
            select(AuditEventRecord)
            .where(AuditEventRecord.case_id == self.case_id)
            .order_by(AuditEventRecord.timestamp)
        )
        events = []
        for r in result.scalars().all():
            events.append(
                AuditEvent(
                    event_id=r.id,
                    case_id=r.case_id,
                    timestamp=r.timestamp,
                    actor=r.actor,
                    action=r.action,
                    inputs_hash=r.inputs_hash,
                    outputs=r.outputs_json,
                    citations=[Citation(**c) for c in r.citations_json],
                    model=r.model,
                    prompt_version=r.prompt_version,
                )
            )
        return events
