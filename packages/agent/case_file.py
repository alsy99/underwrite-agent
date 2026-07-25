from datetime import datetime, timezone

from packages.agent.case_polish import (
    build_open_questions,
    polish_findings,
    policy_finding_description,
    synthesize_executive_summary,
)
from packages.schemas.case import (
    CaseFile,
    Citation,
    Contradiction,
    EntityProfile,
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
        self.entity_profiles: list[EntityProfile] = []
        self.metadata: dict = {}
        self.vertical: str = ""
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
                        description=policy_finding_description(p, self.contradictions),
                        citations=[
                            Citation(
                                doc_id=p.source_policy_doc_id,
                                page=None,
                                span=(p.excerpt or "")[:200],
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

    def set_entity_profiles(self, profiles: list[EntityProfile]) -> None:
        self.entity_profiles = list(profiles)
        for profile in profiles:
            for signal in profile.signals:
                if signal.severity not in ("high", "medium"):
                    continue
                self.add_finding(
                    signal.severity,
                    f"OSINT: {profile.entity_type} — {signal.signal_type}",
                    f"{profile.entity_name}: {signal.summary}",
                )
            if profile.status == "flagged":
                self.open_questions.append(
                    f"Escalate OSINT review for {profile.entity_type} '{profile.entity_name}'"
                )
            if profile.status == "mismatch":
                self.open_questions.append(
                    f"Reconcile identity mismatch for '{profile.entity_name}'"
                )
            if profile.status == "unverified" and profile.entity_type == "business":
                self.open_questions.append(
                    f"Obtain primary-source verification for business '{profile.entity_name}'"
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
        high_contras = sum(1 for c in self.contradictions if c.severity == "high")
        policy_fails = sum(1 for p in self.policy_findings if p.status == "fail")
        high_findings = sum(1 for f in self.findings if f.severity == "high")
        osint_flagged = sum(1 for p in self.entity_profiles if p.status in ("flagged", "mismatch"))
        osint_high = sum(
            1
            for p in self.entity_profiles
            for s in p.signals
            if s.severity == "high"
        )

        # Advisory MVP: auto-decline only when multiple independent high-severity signals agree.
        if high_contras >= 2 and (policy_fails >= 1 or high_findings >= 2):
            return RecommendedAction.DECLINE
        if osint_high >= 2 and (high_contras >= 1 or policy_fails >= 1):
            return RecommendedAction.DECLINE

        if high_contras >= 1 or policy_fails >= 1 or osint_flagged >= 1:
            return RecommendedAction.REVIEW
        if any(p.status == "review" for p in self.policy_findings):
            return RecommendedAction.REVIEW
        if not self.contradictions and self.policy_findings:
            if all(p.status == "pass" for p in self.policy_findings) and not osint_flagged:
                return RecommendedAction.APPROVE
        if not self.contradictions and not any(
            f.severity in ("high", "medium") for f in self.findings
        ):
            return RecommendedAction.APPROVE
        return RecommendedAction.REVIEW

    def build(self, executive_summary: str = "") -> CaseFile:
        action = self.recommend_action()
        self.findings = polish_findings(self.findings)
        self.open_questions = build_open_questions(
            contradictions=self.contradictions,
            policy_findings=self.policy_findings,
            existing=self.open_questions,
            action=action,
            metadata=self.metadata,
        )
        summary = synthesize_executive_summary(
            vertical=self.vertical or "loan",
            action=action,
            findings=self.findings,
            contradictions=self.contradictions,
            policy_findings=self.policy_findings,
            entity_profiles=self.entity_profiles,
            llm_text=executive_summary,
        )
        return CaseFile(
            executive_summary=summary,
            findings=self.findings,
            contradictions=self.contradictions,
            policy_findings=self.policy_findings,
            investigation_timeline=self.timeline,
            recommended_action=action,
            open_questions=self.open_questions,
            entity_profiles=self.entity_profiles,
        )
