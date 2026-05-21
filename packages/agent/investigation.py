from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.agent.case_file import CaseFileBuilder
from packages.agent.tools.registry import ToolRegistry
from packages.audit.logger import AuditLogger
from packages.config import get_settings
from packages.cross_check.engine import CrossCheckEngine
from packages.db.models import CaseRecord
from packages.documents.pipeline import DocumentPipeline
from packages.llm.client import LLMClient
from packages.policy_rag.service import PolicyRAGService
from packages.schemas.case import (
    CaseFile,
    Contradiction,
    LoanVertical,
    PolicyFinding,
    RecommendedAction,
)


class InvestigationRunner:
    """Sherlock investigation pipeline — LangGraph-style explicit stages."""

    PLAN_TOOLS = [
        ("cross_check_narratives", {}),
        ("query_policy_rag", {}),
        ("lookup_business_registry", {"entity_name": "{business_name}"}),
        ("verify_employer_osint", {"employer": "{employer}"}),
        ("geocode_address", {"address": "{address}"}),
        ("address_risk_signals", {"address": "{address}"}),
    ]

    def __init__(self, session: AsyncSession, case_id: str):
        self.session = session
        self.case_id = case_id
        self.settings = get_settings()
        self.llm = LLMClient()

    async def run(self) -> CaseFile:
        case = await self._get_case()
        case.status = "processing"
        await self.session.flush()

        audit = AuditLogger(self.session, case.id)
        builder = CaseFileBuilder()
        doc_pipeline = DocumentPipeline(self.session, case.id, case.tenant_id)
        bundle = await doc_pipeline.get_case_text_bundle()

        vertical = LoanVertical(case.vertical)
        metadata = case.metadata_json or {}

        await audit.log(
            actor="system",
            action="investigation_started",
            inputs={"vertical": case.vertical},
            prompt_version="investigation_v1",
        )

        cross_engine = CrossCheckEngine(self.session, case.id, vertical)
        contradictions = await cross_engine.run(bundle)
        builder.add_contradictions(contradictions)
        builder.log_step("cross_check_narratives", f"Found {len(contradictions)} contradictions")

        policy = PolicyRAGService(self.session)
        policy_findings = await policy.evaluate_case(
            case.tenant_id, case.id, bundle, case.vertical
        )
        builder.add_policy_findings(policy_findings)
        builder.log_step("query_policy_rag", f"{len(policy_findings)} policy findings")

        tools = ToolRegistry(
            self.session, case.id, case.tenant_id, vertical, metadata
        )
        steps_run = 0
        max_steps = self.settings.max_agent_steps

        plan = self._build_plan(metadata)
        await audit.log(
            actor="agent",
            action="plan_created",
            outputs={"steps": plan},
            prompt_version="plan_v1",
        )
        builder.log_step("plan_investigation", f"Planned {len(plan)} tool steps")

        for tool_name, args in plan:
            if steps_run >= max_steps:
                break
            resolved_args = self._resolve_args(args, metadata)
            result = await tools.execute(tool_name, resolved_args, bundle)
            steps_run += 1
            builder.log_step(tool_name, str(result)[:300])
            await audit.log(
                actor="agent",
                action="tool_call",
                inputs={"tool": tool_name, "args": resolved_args},
                outputs=result if isinstance(result, dict) else {"result": str(result)},
                prompt_version="tool_v1",
            )
            self._absorb_tool_results(builder, tool_name, result, contradictions, policy_findings)

        summary = await self._synthesize_brief(builder, bundle, case.vertical)
        case_file = builder.build(summary)
        case.status = "completed"
        case.completed_at = datetime.now(timezone.utc)
        case.case_file_json = case_file.model_dump(mode="json")
        await self.session.commit()
        return case_file

    async def _get_case(self) -> CaseRecord:
        result = await self.session.execute(
            select(CaseRecord).where(CaseRecord.id == self.case_id)
        )
        case = result.scalar_one()
        return case

    def _build_plan(self, metadata: dict[str, Any]) -> list[tuple[str, dict]]:
        plan = []
        for tool, args in self.PLAN_TOOLS:
            plan.append((tool, args))
        if metadata.get("search_queries"):
            for q in metadata["search_queries"][:2]:
                plan.insert(0, ("search_documents", {"query": q}))
        return plan[: self.settings.max_agent_steps]

    def _resolve_args(self, args: dict, metadata: dict) -> dict:
        resolved = {}
        for k, v in args.items():
            if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                key = v[1:-1]
                resolved[k] = metadata.get(key, "")
            else:
                resolved[k] = v
        return resolved

    def _absorb_tool_results(
        self,
        builder: CaseFileBuilder,
        tool: str,
        result: dict,
        existing_contradictions: list[Contradiction],
        existing_policy: list[PolicyFinding],
    ) -> None:
        if tool == "lookup_business_registry" and result.get("status") == "not_found":
            builder.add_finding(
                "medium",
                "Entity registry lookup",
                f"Could not verify entity: {result.get('entity_name')}",
            )
        if tool == "verify_employer_osint" and not result.get("match"):
            builder.add_finding(
                "high",
                "Employer OSINT mismatch",
                f"Stated employer does not match verification target ({result.get('employer')})",
            )
        if tool == "address_risk_signals" and result.get("risk_level") == "high":
            builder.add_finding(
                "medium",
                "Address risk signals",
                f"Signals: {', '.join(result.get('signals', []))}",
            )
            builder.open_questions.append("Confirm business operates at stated address")

    async def _synthesize_brief(
        self, builder: CaseFileBuilder, bundle: str, vertical: str
    ) -> str:
        system = (
            "Write a 1-page executive summary for a human underwriter based ONLY on "
            "the structured findings provided. Be concise and factual."
        )
        facts = {
            "vertical": vertical,
            "contradictions": [c.model_dump() for c in builder.contradictions],
            "policy_findings": [p.model_dump() for p in builder.policy_findings],
            "findings": [f.model_dump() for f in builder.findings],
            "recommended_action": builder.recommend_action().value,
        }
        user = f"Structured facts:\n{facts}"
        text = await self.llm.complete(system, user, prompt_version="brief_v1")
        if not text or len(text) < 50:
            n_contra = len(builder.contradictions)
            n_policy = len(builder.policy_findings)
            action = builder.recommend_action().value
            text = (
                f"Underwriting investigation for {vertical} loan package complete. "
                f"Detected {n_contra} cross-document contradiction(s) and {n_policy} policy finding(s). "
                f"Recommended action: {action}. "
            )
            if n_contra == 0:
                text += "No contradictions detected across configured narrative pairs. "
            text += "See structured findings and audit timeline for evidence."
        return text
