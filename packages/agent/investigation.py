from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.worker.agent_graph import InvestigationState, build_investigation_graph
from packages.agent.case_file import CaseFileBuilder
from packages.agent.entity_names import (
    clean_org_name,
    employers_conflict,
    extract_employer_from_label,
    extract_employer_from_letter,
)
from packages.agent.tools.registry import ToolRegistry
from packages.audit.logger import AuditLogger
from packages.config import get_settings
from packages.cross_check.engine import CrossCheckEngine
from packages.db.models import CaseRecord
from packages.documents.pipeline import DocumentPipeline
from packages.llm.client import LLMClient
from packages.osint.profile import ProfileAnalyzer
from packages.policy_rag.service import PolicyRAGService
from packages.schemas.case import CaseFile, EntityProfile, LoanVertical


# Tools the agent may schedule after cross-check / policy RAG (not re-run those).
INVESTIGATION_TOOLS = {
    "lookup_business_registry",
    "verify_employer_osint",
    "verify_web_presence",
    "check_sanctions",
    "search_adverse_media",
    "lookup_sec_filings",
    "geocode_address",
    "address_risk_signals",
    "search_documents",
    "build_entity_profile",
}

DEFAULT_TOOL_PLAN: list[tuple[str, dict[str, Any]]] = [
    ("lookup_business_registry", {"entity_name": "{business_name}", "ein": "{ein}"}),
    ("verify_employer_osint", {"employer": "{employer}"}),
    ("verify_web_presence", {"entity_name": "{business_name}", "domain": "{domain}"}),
    ("check_sanctions", {"name": "{business_name}"}),
    ("search_adverse_media", {"entity_name": "{business_name}"}),
    ("geocode_address", {"address": "{address}"}),
    ("address_risk_signals", {"address": "{address}"}),
]


class InvestigationRunner:
    """Sherlock investigation pipeline driven by a LangGraph state machine."""

    def __init__(self, session: AsyncSession, case_id: str):
        self.session = session
        self.case_id = case_id
        self.settings = get_settings()
        self.llm = LLMClient()
        self.builder = CaseFileBuilder()
        self.audit: AuditLogger | None = None
        self.case: CaseRecord | None = None
        self.tools: ToolRegistry | None = None

    async def run(self) -> CaseFile:
        graph = build_investigation_graph(self)
        final: InvestigationState = await graph.ainvoke(
            {"case_id": self.case_id, "step_count": 0, "tool_results": [], "timeline": []}
        )
        return CaseFile.model_validate(final["case_file"])

    async def node_intake(self, state: InvestigationState) -> InvestigationState:
        case = await self._get_case()
        self.case = case
        case.status = "processing"
        await self.session.flush()

        self.audit = AuditLogger(self.session, case.id, tenant_id=case.tenant_id)
        doc_pipeline = DocumentPipeline(self.session, case.id, case.tenant_id)
        bundle = await doc_pipeline.get_case_text_bundle()

        metadata = dict(case.metadata_json or {})
        metadata = self._enrich_metadata(metadata, bundle)
        case.metadata_json = metadata
        self.builder.metadata = metadata
        self.builder.vertical = case.vertical

        self.tools = ToolRegistry(
            self.session,
            case.id,
            case.tenant_id,
            LoanVertical(case.vertical),
            metadata,
        )

        await self.audit.log(
            actor="system",
            action="investigation_started",
            inputs={"vertical": case.vertical},
            prompt_version="investigation_v1",
        )
        self.builder.log_step("intake", f"Loaded case {case.id} ({case.vertical})")

        return {
            **state,
            "tenant_id": case.tenant_id,
            "vertical": case.vertical,
            "metadata": metadata,
            "document_bundle": bundle,
        }

    async def node_cross_check(self, state: InvestigationState) -> InvestigationState:
        assert self.case and self.audit
        vertical = LoanVertical(state["vertical"])
        cross_engine = CrossCheckEngine(self.session, self.case.id, vertical)
        contradictions = await cross_engine.run(state["document_bundle"])
        self.builder.add_contradictions(contradictions)
        self.builder.log_step(
            "cross_check_narratives", f"Found {len(contradictions)} contradictions"
        )
        return {**state, "contradictions": contradictions}

    async def node_policy_rag(self, state: InvestigationState) -> InvestigationState:
        assert self.case and self.audit
        policy = PolicyRAGService(self.session)
        policy_findings = await policy.evaluate_case(
            state["tenant_id"],
            self.case.id,
            state["document_bundle"],
            state["vertical"],
        )
        self.builder.add_policy_findings(policy_findings)
        self.builder.log_step("query_policy_rag", f"{len(policy_findings)} policy findings")
        return {**state, "policy_findings": policy_findings}

    async def node_plan(self, state: InvestigationState) -> InvestigationState:
        assert self.audit
        plan = await self._build_dynamic_plan(state)
        await self.audit.log(
            actor="agent",
            action="plan_created",
            outputs={"steps": [{"tool": t, "args": a} for t, a in plan]},
            prompt_version="plan_v1",
        )
        self.builder.log_step("plan_investigation", f"Planned {len(plan)} tool steps")
        return {**state, "plan": plan}

    async def node_agent_loop(self, state: InvestigationState) -> InvestigationState:
        assert self.tools and self.audit
        plan = list(state.get("plan") or [])
        metadata = state.get("metadata") or {}
        results: list[dict[str, Any]] = list(state.get("tool_results") or [])
        steps_run = int(state.get("step_count") or 0)
        max_steps = self.settings.max_agent_steps

        for tool_name, args in plan:
            if steps_run >= max_steps:
                break
            if tool_name not in INVESTIGATION_TOOLS:
                continue
            if tool_name == "build_entity_profile":
                continue  # always fused after loop
            resolved_args = self._resolve_args(args, metadata)
            result = await self.tools.execute(tool_name, resolved_args, state["document_bundle"])
            steps_run += 1
            results.append({"tool": tool_name, "args": resolved_args, "result": result})
            self.builder.log_step(tool_name, str(result)[:300])
            await self.audit.log(
                actor="agent",
                action="tool_call",
                inputs={"tool": tool_name, "args": resolved_args},
                outputs=result if isinstance(result, dict) else {"result": str(result)},
                prompt_version="tool_v1",
            )
            self._absorb_tool_results(tool_name, result)

        # Always fuse EntityProfile(s) from tool results + metadata
        profiles = ProfileAnalyzer().build_profiles(metadata, results)
        self.builder.set_entity_profiles(profiles)
        self.builder.log_step(
            "build_entity_profile",
            f"Built {len(profiles)} entity profile(s)",
        )
        await self.audit.log(
            actor="agent",
            action="tool_call",
            inputs={"tool": "build_entity_profile"},
            outputs={
                "profiles": [p.model_dump(mode="json") for p in profiles],
                "count": len(profiles),
            },
            prompt_version="tool_v1",
        )
        results.append(
            {
                "tool": "build_entity_profile",
                "args": {},
                "result": {
                    "profiles": [p.model_dump(mode="json") for p in profiles],
                    "count": len(profiles),
                },
            }
        )
        steps_run += 1

        return {**state, "tool_results": results, "step_count": steps_run}

    async def node_synthesize(self, state: InvestigationState) -> InvestigationState:
        summary = await self._synthesize_brief(state["vertical"])
        return {**state, "executive_summary": summary}

    async def node_finalize(self, state: InvestigationState) -> InvestigationState:
        assert self.case
        case_file = self.builder.build(state.get("executive_summary") or "")
        self.case.status = "completed"
        self.case.completed_at = datetime.now(timezone.utc)
        self.case.case_file_json = case_file.model_dump(mode="json")
        await self.session.commit()

        try:
            from packages.los import EVENT_CASE_COMPLETED, emit_and_deliver

            await emit_and_deliver(
                self.session,
                tenant_id=self.case.tenant_id,
                event_type=EVENT_CASE_COMPLETED,
                payload={
                    "case_id": self.case.id,
                    "recommended_action": case_file.recommended_action.value,
                    "status": "completed",
                },
            )
        except Exception:
            # Webhooks must not fail investigation completion
            pass

        return {**state, "case_file": case_file.model_dump(mode="json")}

    async def _get_case(self) -> CaseRecord:
        result = await self.session.execute(
            select(CaseRecord).where(CaseRecord.id == self.case_id)
        )
        return result.scalar_one()

    async def _build_dynamic_plan(
        self, state: InvestigationState
    ) -> list[tuple[str, dict[str, Any]]]:
        metadata = state.get("metadata") or {}
        system = (
            "You are an underwriting fraud investigation planner. "
            "Given case metadata and prior findings, choose which tools to run next. "
            "Output JSON only: "
            '{"steps":[{"tool":"lookup_business_registry|verify_employer_osint|'
            "verify_web_presence|check_sanctions|search_adverse_media|lookup_sec_filings|"
            'geocode_address|address_risk_signals|search_documents","args":{...}}]} '
            "Do not include cross_check_narratives, query_policy_rag, or build_entity_profile "
            "— those are handled separately. "
            "Prefer 4-8 high-value tools covering registry, employer, sanctions, address, and web. "
            "Skip tools when required args are empty."
        )
        user = (
            f"Vertical: {state.get('vertical')}\n"
            f"Metadata: {metadata}\n"
            f"Contradiction count: {len(state.get('contradictions') or [])}\n"
            f"Policy finding count: {len(state.get('policy_findings') or [])}\n"
            f"Document excerpt:\n{(state.get('document_bundle') or '')[:4000]}"
        )
        raw = await self.llm.complete_json(system, user, prompt_version="plan_v1")
        plan: list[tuple[str, dict[str, Any]]] = []
        for step in raw.get("steps") or []:
            if not isinstance(step, dict):
                continue
            tool = step.get("tool")
            if tool not in INVESTIGATION_TOOLS or tool == "build_entity_profile":
                continue
            args = step.get("args") if isinstance(step.get("args"), dict) else {}
            plan.append((tool, args))

        if not plan:
            plan = list(DEFAULT_TOOL_PLAN)

        # Ensure core OSINT coverage when metadata present
        plan = self._ensure_core_osint(plan, metadata)

        # Drop tools that would run with empty required args.
        filtered: list[tuple[str, dict[str, Any]]] = []
        for tool, args in plan:
            resolved = self._resolve_args(args, metadata)
            if tool == "lookup_business_registry" and not (
                resolved.get("entity_name") or metadata.get("business_name")
            ):
                continue
            if tool == "verify_employer_osint" and not (
                resolved.get("employer")
                or metadata.get("employer")
                or metadata.get("stated_employer")
            ):
                continue
            if tool in ("geocode_address", "address_risk_signals") and not (
                resolved.get("address") or metadata.get("address")
            ):
                continue
            if tool == "search_documents" and not resolved.get("query"):
                continue
            if tool in (
                "verify_web_presence",
                "search_adverse_media",
                "lookup_sec_filings",
            ) and not (
                resolved.get("entity_name") or metadata.get("business_name")
            ):
                continue
            if tool == "check_sanctions" and not (
                resolved.get("name")
                or metadata.get("business_name")
                or metadata.get("applicant_name")
            ):
                continue
            # Fill placeholder defaults from metadata when LLM omitted args.
            if tool == "lookup_business_registry" and not resolved.get("entity_name"):
                args = {**args, "entity_name": "{business_name}", "ein": "{ein}"}
            if tool == "verify_employer_osint" and not resolved.get("employer"):
                args = {**args, "employer": "{employer}"}
            if tool in ("geocode_address", "address_risk_signals") and not resolved.get(
                "address"
            ):
                args = {**args, "address": "{address}"}
            if tool == "verify_web_presence" and not resolved.get("entity_name"):
                args = {**args, "entity_name": "{business_name}", "domain": "{domain}"}
            if tool == "check_sanctions" and not resolved.get("name"):
                args = {**args, "name": "{business_name}"}
            if tool in ("search_adverse_media", "lookup_sec_filings") and not resolved.get(
                "entity_name"
            ):
                args = {**args, "entity_name": "{business_name}"}
            filtered.append((tool, args))

        if metadata.get("search_queries"):
            for q in metadata["search_queries"][:2]:
                filtered.insert(0, ("search_documents", {"query": q}))

        # Also screen principal when present
        if metadata.get("applicant_name"):
            filtered.append(("check_sanctions", {"name": "{applicant_name}"}))

        # Deduplicate by tool+resolved key arg
        seen: set[str] = set()
        unique: list[tuple[str, dict[str, Any]]] = []
        for tool, args in filtered:
            resolved = self._resolve_args(args, metadata)
            key = f"{tool}:{resolved.get('entity_name') or resolved.get('name') or resolved.get('employer') or resolved.get('address') or resolved.get('query')}"
            if key in seen:
                continue
            seen.add(key)
            unique.append((tool, args))

        return unique[: max(self.settings.max_agent_steps - 1, 1)]

    def _ensure_core_osint(
        self, plan: list[tuple[str, dict[str, Any]]], metadata: dict[str, Any]
    ) -> list[tuple[str, dict[str, Any]]]:
        have = {t for t, _ in plan}
        extras: list[tuple[str, dict[str, Any]]] = []
        for tool, args in DEFAULT_TOOL_PLAN:
            if tool in have:
                continue
            extras.append((tool, args))
        return plan + extras

    def _resolve_args(self, args: dict, metadata: dict) -> dict:
        resolved = {}
        for k, v in args.items():
            if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                key = v[1:-1]
                resolved[k] = metadata.get(key, "")
            else:
                resolved[k] = v
        return resolved

    def _enrich_metadata(self, metadata: dict[str, Any], bundle: str) -> dict[str, Any]:
        enriched = dict(metadata)
        for key in ("employer", "stated_employer", "employer_from_letter", "business_name"):
            if enriched.get(key):
                cleaned = clean_org_name(str(enriched[key]))
                if cleaned:
                    enriched[key] = cleaned

        if not enriched.get("business_name"):
            m = re.search(
                r"(?:business(?:\s+(?:legal\s+)?name)?|applicant|borrower|entity)\s*[:\-]\s*"
                r"([A-Za-z0-9 &.,'\-]+(?:LLC|Inc\.?|LP|Corp\.?)?)",
                bundle,
                re.IGNORECASE,
            )
            if m:
                name = clean_org_name(m.group(1))
                if name:
                    enriched["business_name"] = name

        if not enriched.get("employer") and not enriched.get("stated_employer"):
            labeled = extract_employer_from_label(bundle)
            if labeled:
                enriched["employer"] = labeled
                enriched.setdefault("stated_employer", labeled)

        if not enriched.get("address"):
            m = re.search(
                r"(?:address|located at|property|business address)\s*[:\-]\s*([^\n]{10,120})",
                bundle,
                re.IGNORECASE,
            )
            if m:
                enriched["address"] = m.group(1).strip().rstrip(".")
        if enriched.get("employer") and not enriched.get("stated_employer"):
            enriched["stated_employer"] = clean_org_name(str(enriched["employer"])) or enriched[
                "employer"
            ]

        if not enriched.get("ein"):
            m = re.search(r"\bEIN\s*[:#]?\s*(\d{2}-\d{7})\b", bundle, re.IGNORECASE)
            if m:
                enriched["ein"] = m.group(1)

        if not enriched.get("applicant_name"):
            m = re.search(
                r"(?:applicant(?:\s+name)?|borrower)\s*[:\-]\s*([A-Za-z][A-Za-z .'\-]{2,60})",
                bundle,
                re.IGNORECASE,
            )
            if m:
                name = m.group(1).strip().rstrip(".")
                if "llc" not in name.lower() and "inc" not in name.lower():
                    enriched["applicant_name"] = name

        if not enriched.get("domain"):
            m = re.search(
                r"(?:website|domain|url)\s*[:\-]\s*(https?://)?([a-z0-9.-]+\.[a-z]{2,})",
                bundle,
                re.IGNORECASE,
            )
            if m:
                enriched["domain"] = m.group(2).lower()

        letter_emp = extract_employer_from_letter(bundle)
        if letter_emp:
            enriched["employer_from_letter"] = letter_emp
            stated = enriched.get("stated_employer") or enriched.get("employer")
            if stated and employers_conflict(str(stated), letter_emp):
                enriched["employer"] = letter_emp
            elif not stated:
                enriched["employer"] = letter_emp

        return enriched

    def _absorb_tool_results(self, tool: str, result: dict) -> None:
        # Immediate open questions; EntityProfile fusion owns structured OSINT findings.
        if tool == "address_risk_signals" and result.get("risk_level") == "high":
            self.builder.open_questions.append(
                "Confirm business operates at stated address"
            )
        if tool == "check_sanctions" and result.get("status") in ("hit", "possible_match"):
            self.builder.open_questions.append(
                f"Complete sanctions due diligence for {result.get('name')}"
            )
        if tool == "verify_employer_osint" and not result.get("match"):
            stated = self.builder.metadata.get("stated_employer") or self.builder.metadata.get(
                "employer"
            )
            letter = self.builder.metadata.get("employer_from_letter")
            if stated and letter:
                self.builder.open_questions.append(
                    "Please provide a written explanation for the employer name discrepancy "
                    f"between the application ({stated}) and the employment letter ({letter})."
                )
            else:
                self.builder.open_questions.append(
                    "Please provide a written explanation for the employer name discrepancy "
                    "between the application and the employment letter."
                )

    async def _synthesize_brief(self, vertical: str) -> str:
        system = (
            "Write an executive summary for a human underwriter in 3-5 complete sentences "
            "of professional prose. Synthesize key risks only. No bullets, no JSON, "
            "no headings, no repetition of full policy text. Base ONLY on structured facts."
        )
        facts = {
            "vertical": vertical,
            "contradictions": [c.model_dump() for c in self.builder.contradictions],
            "policy_findings": [p.model_dump() for p in self.builder.policy_findings],
            "findings": [f.model_dump() for f in self.builder.findings[:12]],
            "entity_profiles": [
                p.model_dump(mode="json") if isinstance(p, EntityProfile) else p
                for p in self.builder.entity_profiles
            ],
            "recommended_action": self.builder.recommend_action().value,
        }
        user = f"Structured facts:\n{facts}"
        return await self.llm.complete(system, user, prompt_version="brief_v2")
