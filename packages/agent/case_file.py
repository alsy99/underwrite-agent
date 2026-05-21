from datetime import datetime, timezone

from packages.schemas.case import (
    CaseFile,
    Citation,
    Contradiction,
    Finding,
    InvestigationStep,
    PolicyFinding,
    RecommendedAction,
)


class CaseFileBuilder:
    def __init__(self):
        self.findings: list[Finding] = []
        self.contradictions: list[Contradiction] = []
        self.policy_findings: list[PolicyFinding] = []
        self.timeline: list[InvestigationStep] = []
        self.open_questions: list[str] = []
        self._step = 0

    def add_contradictions(self, items: list[Contradiction]) -> None:
        self.contradictions.extend(items)
        for c in items:
            self.findings.append(
                Finding(
                    id=f"finding_{len(self.findings)+1}",
                    severity=c.severity,
                    title="Cross-document contradiction",
                    description=f"{c.claim_a} vs {c.claim_b}",
                    citations=[
                        Citation(doc_id=d, page=None, span=c.quoted_evidence[:200])
                        for d in c.source_doc_ids
                    ],
                )
            )

    def add_policy_findings(self, items: list[PolicyFinding]) -> None:
        self.policy_findings.extend(items)
        for p in items:
            if p.status in ("fail", "review"):
                self.findings.append(
                    Finding(
                        id=f"finding_{len(self.findings)+1}",
                        severity="high" if p.status == "fail" else "medium",
                        title=f"Policy {p.rule_ref}",
                        description=p.excerpt,
                        citations=[
                            Citation(
                                doc_id=p.source_policy_doc_id,
                                page=None,
                                span=p.excerpt[:200],
                            )
                        ],
                    )
                )

    def add_finding(self, severity: str, title: str, description: str, doc_id: str = "") -> None:
        citations = [Citation(doc_id=doc_id, page=None, span=None)] if doc_id else []
        self.findings.append(
            Finding(
                id=f"finding_{len(self.findings)+1}",
                severity=severity,
                title=title,
                description=description,
                citations=citations,
            )
        )

    def log_step(self, tool: str, summary: str) -> None:
        self._step += 1
        self.timeline.append(
            InvestigationStep(
                step=self._step,
                tool=tool,
                summary=summary,
                timestamp=datetime.now(timezone.utc),
            )
        )

    def recommend_action(self) -> RecommendedAction:
        if any(c.severity == "high" for c in self.contradictions):
            return RecommendedAction.REVIEW
        if any(p.status == "fail" for p in self.policy_findings):
            return RecommendedAction.REVIEW
        if any(p.status == "review" for p in self.policy_findings):
            return RecommendedAction.REVIEW
        if not self.contradictions and self.policy_findings:
            if all(p.status == "pass" for p in self.policy_findings):
                return RecommendedAction.APPROVE
        if not self.contradictions and not any(
            f.severity in ("high", "medium") for f in self.findings
        ):
            return RecommendedAction.APPROVE
        return RecommendedAction.REVIEW

    def build(self, executive_summary: str) -> CaseFile:
        action = self.recommend_action()
        if action == RecommendedAction.REVIEW and not self.open_questions:
            self.open_questions = [
                "Confirm employer and revenue documentation with primary sources",
                "Validate business address is not a virtual office",
            ]
        return CaseFile(
            executive_summary=executive_summary,
            findings=self.findings,
            contradictions=self.contradictions,
            policy_findings=self.policy_findings,
            investigation_timeline=self.timeline,
            recommended_action=action,
            open_questions=self.open_questions,
        )
