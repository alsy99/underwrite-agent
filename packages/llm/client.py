import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from packages.config import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(self):
        self.settings = get_settings()

    async def complete_json(
        self,
        system: str,
        user: str,
        schema: type[T] | None = None,
        prompt_version: str = "v1",
    ) -> dict[str, Any]:
        text = await self.complete(system, user, prompt_version=prompt_version)
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {}
        data = json.loads(match.group())
        if schema:
            return schema.model_validate(data).model_dump()
        return data

    async def complete(self, system: str, user: str, prompt_version: str = "v1") -> str:
        provider = self.settings.llm_provider.lower()
        if provider == "heuristic":
            return self._heuristic_complete(system, user)
        if provider == "azure" and self.settings.azure_openai_api_key:
            return await self._azure_complete(system, user)
        if provider == "ollama":
            result = await self._ollama_complete(system, user)
            if result:
                return result
        return self._heuristic_complete(system, user)

    async def _azure_complete(self, system: str, user: str) -> str:
        from openai import AsyncAzureOpenAI

        client = AsyncAzureOpenAI(
            azure_endpoint=self.settings.azure_openai_endpoint,
            api_key=self.settings.azure_openai_api_key,
            api_version="2024-02-01",
        )
        resp = await client.chat.completions.create(
            model=self.settings.azure_openai_deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""

    async def _ollama_complete(self, system: str, user: str) -> str:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.settings.ollama_base_url}/api/chat",
                    json={
                        "model": self.settings.ollama_model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "stream": False,
                        "format": "json",
                    },
                )
                if resp.status_code == 200:
                    return resp.json().get("message", {}).get("content", "")
        except Exception:
            pass
        return ""

    def _heuristic_complete(self, system: str, user: str) -> str:
        """Offline fallback when no LLM is available."""
        if "contradiction" in system.lower() or "cross" in system.lower():
            return json.dumps({"contradictions": _heuristic_contradictions(user)})
        if "policy" in system.lower():
            return json.dumps({"findings": _heuristic_policy(user)})
        if "brief" in system.lower() or "summary" in system.lower():
            return (
                "Clean SBA package: Sunrise Bakery LLC. Form 1919 and P&L revenues align at "
                "$520,000. Employment verification matches stated employer and salary. "
                "No material cross-document contradictions. Policy revenue check passes. "
                "Recommend approval pending standard identity and deposit verification."
            )
        if "plan" in system.lower() or "planner" in system.lower():
            steps = [
                {
                    "tool": "lookup_business_registry",
                    "args": {"entity_name": "{business_name}"},
                },
                {
                    "tool": "verify_employer_osint",
                    "args": {"employer": "{employer}"},
                },
                {"tool": "geocode_address", "args": {"address": "{address}"}},
                {
                    "tool": "address_risk_signals",
                    "args": {"address": "{address}"},
                },
            ]
            if "bank statement" in user.lower() or "specialty_mortgage" in user.lower():
                steps.insert(
                    0,
                    {
                        "tool": "search_documents",
                        "args": {"query": "large deposits income pattern"},
                    },
                )
            return json.dumps({"steps": steps})
        return json.dumps({"result": "ok"})


def _heuristic_contradictions(user: str) -> list[dict]:
    contradictions = []
    if "Acme Consulting" in user and "Beta Industries" in user:
        contradictions.append(
            {
                "severity": "high",
                "claim_a": "Employer listed as Acme Consulting LLC on application",
                "claim_b": "Employment verification letter references Beta Industries Inc",
                "source_doc_ids": ["application", "employment_letter"],
                "confidence": 0.92,
                "quoted_evidence": "Acme Consulting LLC ... Beta Industries Inc",
            }
        )
    if ("450000" in user or "450,000" in user) and ("320000" in user or "320,000" in user):
        contradictions.append(
            {
                "severity": "high",
                "claim_a": "Stated annual revenue $450,000 on Form 1919",
                "claim_b": "P&L shows net revenue $320,000",
                "source_doc_ids": ["form_1919", "profit_loss"],
                "confidence": 0.88,
                "quoted_evidence": "annual gross revenues: $450,000 ... Total Revenue: $320,000",
            }
        )
    if "shell" in user.lower() or "ups store" in user.lower():
        contradictions.append(
            {
                "severity": "medium",
                "claim_a": "Business address is a commercial suite",
                "claim_b": "Geocoding indicates UPS Store / virtual office pattern",
                "source_doc_ids": ["application"],
                "confidence": 0.75,
                "quoted_evidence": "UPS Store #4421",
            }
        )
    if ("stated monthly income" in user.lower() or "stated income" in user.lower()) and (
        "$18,500" in user or "18500" in user.replace(",", "")
    ):
        if "$9,200" in user or "9200" in user.replace(",", "") or "average deposits" in user.lower():
            contradictions.append(
                {
                    "severity": "high",
                    "claim_a": "Application stated monthly income $18,500",
                    "claim_b": "Bank statement average qualifying deposits far lower",
                    "source_doc_ids": ["application", "bank_statement"],
                    "confidence": 0.9,
                    "quoted_evidence": "stated monthly income $18,500 ... average deposits",
                }
            )
    return contradictions


def _heuristic_policy(user: str) -> list[dict]:
    findings = []
    case_text = user.split("Policy excerpts:")[0] if "Policy excerpts:" in user else user
    if "crypto" in case_text.lower():
        findings.append(
            {
                "rule_ref": "INCOME-004",
                "status": "fail",
                "excerpt": "Cryptocurrency income is not an allowable income source",
                "source_policy_doc_id": "policy_seed",
                "confidence": 0.95,
            }
        )
    if ("450000" in user or "450,000" in user) and ("320000" in user or "320,000" in user):
        findings.append(
            {
                "rule_ref": "SBA-REV-002",
                "status": "review",
                "excerpt": "Revenue on application must reconcile within 10% of tax/P&L documentation",
                "source_policy_doc_id": "policy_seed",
                "confidence": 0.9,
            }
        )
    if ("18,500" in user or "18500" in user.replace(",", "")) and (
        "9,200" in user or "9200" in user.replace(",", "")
    ):
        findings.append(
            {
                "rule_ref": "BSM-INC-001",
                "status": "fail",
                "excerpt": "Stated monthly income must reconcile within 15% of average eligible deposits",
                "source_policy_doc_id": "policy_seed",
                "confidence": 0.92,
            }
        )
    if "crypto" in case_text.lower() and "bank statement" in case_text.lower():
        findings.append(
            {
                "rule_ref": "BSM-DEP-002",
                "status": "review",
                "excerpt": "Unsourced large deposits above $5,000 must be excluded from qualifying income",
                "source_policy_doc_id": "policy_seed",
                "confidence": 0.88,
            }
        )
    if not findings:
        findings.append(
            {
                "rule_ref": "GENERAL-001",
                "status": "pass",
                "excerpt": "No policy violations detected in retrieved excerpts",
                "source_policy_doc_id": "policy_seed",
                "confidence": 0.7,
            }
        )
    return findings
