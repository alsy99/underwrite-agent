from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LoanVertical(str, Enum):
    SBA_7A = "sba_7a"
    CRE_ACQUISITION = "cre_acquisition"
    SPECIALTY_MORTGAGE = "specialty_mortgage_bank_statement"


class CaseStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RecommendedAction(str, Enum):
    APPROVE = "approve"
    REVIEW = "review"
    DECLINE = "decline"


class Citation(BaseModel):
    doc_id: str
    page: int | None = None
    span: str | None = None


class Contradiction(BaseModel):
    severity: str
    claim_a: str
    claim_b: str
    source_doc_ids: list[str]
    confidence: float
    quoted_evidence: str


class PolicyFinding(BaseModel):
    rule_ref: str
    status: str
    excerpt: str
    source_policy_doc_id: str
    confidence: float = 0.8


class Finding(BaseModel):
    id: str
    severity: str
    title: str
    description: str
    citations: list[Citation] = Field(default_factory=list)


class InvestigationStep(BaseModel):
    step: int
    tool: str
    summary: str
    timestamp: datetime


class OsintSignal(BaseModel):
    source: str
    signal_type: str
    severity: str
    summary: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0


class EntityProfile(BaseModel):
    entity_name: str
    entity_type: str  # business|principal|employer|address
    identity_confidence: float = 0.0
    risk_score: float = 0.0
    status: str = "unverified"  # corroborated|partial|unverified|mismatch|flagged
    registry: dict[str, Any] | None = None
    web_presence: dict[str, Any] | None = None
    sanctions: dict[str, Any] | None = None
    adverse_media: list[dict[str, Any]] = Field(default_factory=list)
    address: dict[str, Any] | None = None
    principals: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[OsintSignal] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)


class VarianceFinding(BaseModel):
    metric: str
    stated: float | None = None
    spread: float | None = None
    variance_pct: float | None = None
    threshold_pct: float = 0.10
    severity: str = "medium"
    summary: str = ""


class CaseFile(BaseModel):
    executive_summary: str
    findings: list[Finding] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    policy_findings: list[PolicyFinding] = Field(default_factory=list)
    investigation_timeline: list[InvestigationStep] = Field(default_factory=list)
    recommended_action: RecommendedAction = RecommendedAction.REVIEW
    open_questions: list[str] = Field(default_factory=list)
    entity_profiles: list[EntityProfile] = Field(default_factory=list)
    spreads_summary: list[VarianceFinding] = Field(default_factory=list)
    memo_version: int | None = None


class CaseCreateRequest(BaseModel):
    vertical: LoanVertical
    tenant_id: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaseListItem(BaseModel):
    case_id: str
    status: CaseStatus
    vertical: LoanVertical
    tenant_id: str
    created_at: datetime
    completed_at: datetime | None = None
    recommended_action: RecommendedAction | None = None
    findings_count: int = 0
    contradictions_count: int = 0


class CaseResponse(BaseModel):
    case_id: str
    status: CaseStatus
    vertical: LoanVertical
    tenant_id: str
    created_at: datetime
    completed_at: datetime | None = None
    case_file: CaseFile | None = None
    error: str | None = None
