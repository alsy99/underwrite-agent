"""Backend unit: entity name cleanup + case polish helpers."""

import pytest

from packages.agent.case_polish import (
    build_open_questions,
    dedupe_findings,
    polish_findings,
    policy_finding_description,
)
from packages.agent.entity_names import (
    clean_org_name,
    employers_conflict,
    extract_employer_from_letter,
)
from packages.schemas.case import (
    Contradiction,
    Finding,
    PolicyFinding,
    RecommendedAction,
)


@pytest.mark.unit
def test_clean_org_stops_at_role():
    assert clean_org_name("Beta Industries Inc as Senior Ops") == "Beta Industries Inc"


@pytest.mark.unit
def test_extract_employer_ignores_since_inc_false_positive():
    text = (
        "John Smith is employed full-time by Beta Industries Inc as "
        "Senior Operations Manager since June 2020."
    )
    assert extract_employer_from_letter(text) == "Beta Industries Inc"


@pytest.mark.unit
def test_employers_conflict_basic():
    assert not employers_conflict("Acme Consulting LLC", "Acme Consulting LLC")
    assert employers_conflict("Acme Consulting LLC", "Beta Industries Inc")
    # Too-short strings clean to empty → no conflict signal
    assert not employers_conflict("A", "Beta Industries Inc")
    assert clean_org_name("A") == ""


@pytest.mark.unit
def test_dedupe_keeps_higher_severity():
    findings = [
        Finding(id="1", severity="low", title="Policy X", description="same"),
        Finding(id="2", severity="high", title="Policy X", description="same"),
    ]
    out = dedupe_findings(findings)
    assert len(out) == 1
    assert out[0].severity == "high"


@pytest.mark.unit
def test_polish_caps_volume():
    findings = [
        Finding(id=f"f{i}", severity="medium", title=f"T{i}", description=f"d{i}")
        for i in range(20)
    ]
    assert len(polish_findings(findings)) <= 12


@pytest.mark.unit
def test_policy_description_uses_contradiction():
    p = PolicyFinding(
        rule_ref="EMP-1",
        status="fail",
        excerpt="Employer named on the loan application must match third-party letters " * 5,
        source_policy_doc_id="p1",
    )
    c = Contradiction(
        severity="high",
        claim_a="Employer Acme",
        claim_b="Employer Beta",
        source_doc_ids=["a"],
        confidence=0.9,
        quoted_evidence="x",
    )
    desc = policy_finding_description(p, [c])
    assert "FAIL" in desc
    assert "Acme" in desc and "Beta" in desc
    assert len(desc) < 280


@pytest.mark.unit
def test_open_questions_specific():
    qs = build_open_questions(
        contradictions=[],
        policy_findings=[],
        existing=[],
        action=RecommendedAction.REVIEW,
        metadata={
            "stated_employer": "Acme Consulting LLC",
            "employer_from_letter": "Beta Industries Inc",
        },
    )
    assert any("Acme Consulting LLC" in q and "Beta Industries Inc" in q for q in qs)
