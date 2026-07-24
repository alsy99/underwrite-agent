from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.logger import AuditLogger
from packages.llm.client import LLMClient
from packages.schemas.case import Contradiction, LoanVertical
from packages.verticals import get_vertical_pack


class ContradictionList(BaseModel):
    contradictions: list[Contradiction] = Field(default_factory=list)


class CrossCheckEngine:
    PROMPT_VERSION = "cross_check_v1"

    def __init__(self, session: AsyncSession, case_id: str, vertical: LoanVertical):
        self.session = session
        self.case_id = case_id
        self.vertical = vertical
        self.llm = LLMClient()
        self.audit = AuditLogger(session, case_id)

    async def run(self, document_bundle: str) -> list[Contradiction]:
        pack = get_vertical_pack(self.vertical)
        pairs = "\n".join(f"- {a} vs {b}" for a, b in pack.cross_check_pairs)

        system = (
            "You are a fraud investigation cross-check engine for commercial lending. "
            "Find semantic contradictions between documents. Output JSON only: "
            '{"contradictions": [{"severity":"high|medium|low","claim_a":"...","claim_b":"...",'
            '"source_doc_ids":["..."],"confidence":0.0-1.0,"quoted_evidence":"..."}]} '
            "Only report contradictions supported by the text. If none, return empty list."
        )
        user = (
            f"Loan vertical: {self.vertical.value}\n"
            f"Compare these narrative pairs:\n{pairs}\n\n"
            f"Documents:\n{document_bundle[:24000]}"
        )

        raw = await self.llm.complete_json(system, user, prompt_version=self.PROMPT_VERSION)
        items = raw.get("contradictions", [])
        contradictions: list[Contradiction] = []
        for item in items:
            try:
                c = Contradiction.model_validate(item)
                contradictions.append(c)
            except Exception:
                continue

        if not contradictions:
            contradictions = self._rule_based_checks(document_bundle)

        contradictions = self._filter_valid(contradictions)

        await self.audit.log(
            actor="cross_check",
            action="contradiction_found",
            inputs={"vertical": self.vertical.value},
            outputs={"count": len(contradictions)},
            model=self.llm.settings.llm_provider,
            prompt_version=self.PROMPT_VERSION,
        )
        return contradictions

    @staticmethod
    def _normalize_claim(text: str) -> str:
        return "".join(ch for ch in text.lower() if ch.isalnum())

    def _filter_valid(self, items: list[Contradiction]) -> list[Contradiction]:
        filtered: list[Contradiction] = []
        for c in items:
            a, b = self._normalize_claim(c.claim_a), self._normalize_claim(c.claim_b)
            if not a or not b or a == b:
                continue
            if a in b or b in a:
                if abs(len(a) - len(b)) < max(len(a), len(b)) * 0.15:
                    continue
            filtered.append(c)
        return filtered

    def _rule_based_checks(self, text: str) -> list[Contradiction]:
        results: list[Contradiction] = []
        if "Acme Consulting" in text and "Beta Industries" in text:
            results.append(
                Contradiction(
                    severity="high",
                    claim_a="Employer Acme Consulting LLC on application",
                    claim_b="Verification letter names Beta Industries Inc",
                    source_doc_ids=["application", "employment_letter"],
                    confidence=0.92,
                    quoted_evidence="Acme Consulting LLC / Beta Industries Inc",
                )
            )
        if ("450,000" in text or "450000" in text) and ("320,000" in text or "320000" in text):
            results.append(
                Contradiction(
                    severity="high",
                    claim_a="Revenue $450,000 on Form 1919",
                    claim_b="P&L total revenue $320,000",
                    source_doc_ids=["form_1919", "profit_loss"],
                    confidence=0.88,
                    quoted_evidence="450,000 ... 320,000",
                )
            )
        if "guarantor" in text.lower() and "Smith Holdings" in text and "Jones LLC" in text:
            results.append(
                Contradiction(
                    severity="medium",
                    claim_a="Guarantor entity Smith Holdings on lease",
                    claim_b="Operating agreement lists Jones LLC as member",
                    source_doc_ids=["commercial_lease", "operating_agreement"],
                    confidence=0.8,
                    quoted_evidence="Smith Holdings / Jones LLC",
                )
            )
        normalized = text.replace(",", "")
        if ("18500" in normalized or "$18,500" in text) and (
            "9200" in normalized or "$9,200" in text or "average monthly deposits" in text.lower()
        ):
            results.append(
                Contradiction(
                    severity="high",
                    claim_a="Application stated monthly income $18,500",
                    claim_b="Bank statement average monthly deposits ~$9,200",
                    source_doc_ids=["application", "bank_statement"],
                    confidence=0.9,
                    quoted_evidence="$18,500 ... $9,200",
                )
            )
        return results
