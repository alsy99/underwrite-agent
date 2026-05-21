from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.schemas.case import Citation


class AuditEvent(BaseModel):
    event_id: str
    case_id: str
    timestamp: datetime
    actor: str
    action: str
    inputs_hash: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    model: str | None = None
    prompt_version: str | None = None
