from packages.cross_check.engine import CrossCheckEngine
from packages.schemas.case import LoanVertical


def test_rule_based_contradictions_fraudulent_sba():
    bundle = """
    [DOC type=form_1919] Acme Consulting LLC annual gross revenues: $450,000
    [DOC type=profit_loss] Total Revenue: $320,000
    [DOC type=employment_letter] Beta Industries Inc employs John Smith
    Application employer: Acme Consulting LLC
    """
    engine = CrossCheckEngine.__new__(CrossCheckEngine)
    results = CrossCheckEngine._rule_based_checks(engine, bundle)
    assert len(results) >= 2
    severities = {r.severity for r in results}
    assert "high" in severities


def test_rule_based_clean_package():
    bundle = """
    Sunrise Bakery LLC revenues $520,000
    P&L Total Revenue: $515,000
    Maria Garcia employed by Sunrise Bakery LLC
    """
    engine = CrossCheckEngine.__new__(CrossCheckEngine)
    results = CrossCheckEngine._rule_based_checks(engine, bundle)
    assert len(results) == 0


def test_vertical_pack_sba_pairs():
    from packages.verticals import get_vertical_pack

    pack = get_vertical_pack(LoanVertical.SBA_7A)
    assert "form_1919" in pack.required_doc_types[0] or "form_1919" in pack.required_doc_types
    assert len(pack.cross_check_pairs) >= 3
