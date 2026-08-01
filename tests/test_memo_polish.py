"""Memo polish: dedupe, ranking, entity cleanup, open questions."""

from packages.agent.case_file import CaseFileBuilder
from packages.agent.case_polish import polish_findings, synthesize_executive_summary
from packages.agent.entity_names import clean_org_name
from packages.memo import build_memo_context, render_memo
from packages.schemas.case import (
    Contradiction,
    Finding,
    PolicyFinding,
    RecommendedAction,
)


def test_clean_org_strips_role_tail():
    assert (
        clean_org_name("Beta Industries Inc as Senior Operations Manager sinc")
        == "Beta Industries Inc"
    )


def test_dedupe_and_rank_findings():
    findings = [
        Finding(
            id="finding_1",
            severity="medium",
            title="Policy EMP-1",
            description="FAIL: employer mismatch",
        ),
        Finding(
            id="finding_2",
            severity="high",
            title="Policy EMP-1",
            description="FAIL: employer mismatch",
        ),
        Finding(
            id="finding_3",
            severity="high",
            title="Cross-document contradiction",
            description="Acme vs Beta",
        ),
        Finding(
            id="finding_4",
            severity="low",
            title="Noise",
            description="minor",
        ),
    ]
    out = polish_findings(findings)
    assert len(out) == 3  # exact dup collapsed
    assert out[0].severity == "high"
    assert "contradiction" in out[0].title.lower() or "Policy" in out[0].title


def test_case_file_build_polishes_memo_inputs():
    builder = CaseFileBuilder()
    builder.vertical = "sba_7a"
    builder.metadata = {
        "stated_employer": "Acme Consulting LLC",
        "employer_from_letter": "Beta Industries Inc",
        "annual_revenue": "450000",
    }
    builder.add_contradictions(
        [
            Contradiction(
                severity="high",
                claim_a="Employer Acme Consulting LLC",
                claim_b="Employer Beta Industries Inc",
                source_doc_ids=["form_1919", "employment_letter"],
                confidence=0.9,
                quoted_evidence="Acme vs Beta",
            )
        ]
    )
    builder.add_policy_findings(
        [
            PolicyFinding(
                rule_ref="EMP-MATCH",
                status="fail",
                excerpt=(
                    "Employer named on the loan application must match third-party "
                    "employment verification letters. Mismatches are treated as potential "
                    "fraud indicators. Additional boilerplate that should not spam the memo."
                ),
                source_policy_doc_id="policy",
            ),
            PolicyFinding(
                rule_ref="EMP-MATCH",
                status="fail",
                excerpt=(
                    "Employer named on the loan application must match third-party "
                    "employment verification letters. Mismatches are treated as potential "
                    "fraud indicators. Additional boilerplate that should not spam the memo."
                ),
                source_policy_doc_id="policy",
            ),
        ]
    )
    cf = builder.build("not useful")
    assert "as Senior" not in cf.executive_summary
    assert cf.findings[0].severity == "high"
    titles = [f.title for f in cf.findings]
    assert titles.count("Policy EMP-MATCH") <= 1
    assert any("employer name discrepancy" in q.lower() for q in cf.open_questions)
    assert "Acme Consulting LLC" in " ".join(cf.open_questions)
    assert "Beta Industries Inc" in " ".join(cf.open_questions)
    policy_f = next(f for f in cf.findings if f.title.startswith("Policy"))
    assert len(policy_f.description) < 280
    assert "FAIL" in policy_f.description

    ctx = build_memo_context(
        case_id="c1",
        vertical="sba_7a",
        tenant_id="default",
        metadata={
            "employer": "Beta Industries Inc as Senior Operations Manager sinc",
            "stated_employer": "Acme Consulting LLC",
        },
        case_file=cf,
    )
    assert ctx["metadata"]["employer"] == "Beta Industries Inc"
    body = render_memo("sba_7a", ctx)
    assert "### High" in body
    assert "as Senior Operations Manager" not in body


def test_open_question_for_deposit_vs_revenue():
    from packages.agent.case_polish import build_open_questions

    qs = build_open_questions(
        contradictions=[
            Contradiction(
                severity="high",
                claim_a="Stated annual revenue $450000",
                claim_b="Irregular large deposits totaling $82000",
                source_doc_ids=["bank"],
                confidence=0.9,
                quoted_evidence="wire $45,000",
            )
        ],
        policy_findings=[],
        existing=[],
        action=RecommendedAction.REVIEW,
        metadata={"annual_revenue": "450000"},
    )
    assert any("bank statements" in q.lower() and "450000" in q for q in qs)
    text = synthesize_executive_summary(
        vertical="sba_7a",
        action=RecommendedAction.REVIEW,
        findings=[
            Finding(
                id="finding_1",
                severity="high",
                title="Cross-document contradiction",
                description="Acme vs Beta",
            )
        ],
        contradictions=[
            Contradiction(
                severity="high",
                claim_a="Acme",
                claim_b="Beta",
                source_doc_ids=["a"],
                confidence=0.9,
                quoted_evidence="x",
            )
        ],
        policy_findings=[],
        entity_profiles=[],
        llm_text='{"Executive Summary": "bad"}',
    )
    assert "recommended action of review" in text.lower()
    assert "Acme" in text and "Beta" in text
