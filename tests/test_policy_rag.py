from packages.llm.client import _heuristic_policy


def test_heuristic_policy_revenue_mismatch():
    context = "Revenue $450,000 on form and $320,000 on P&L"
    findings = _heuristic_policy(context)
    refs = [f["rule_ref"] for f in findings]
    assert "SBA-REV-002" in refs


def test_heuristic_policy_crypto_fail():
    findings = _heuristic_policy("Applicant income from crypto mining")
    assert any(f["status"] == "fail" for f in findings)


def test_heuristic_policy_pass_default():
    findings = _heuristic_policy("Clean application with consistent docs")
    assert any(f["status"] == "pass" for f in findings)
