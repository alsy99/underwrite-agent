from packages.cross_check.engine import CrossCheckEngine
from packages.schemas.case import Contradiction


def test_filter_removes_identical_claims():
    engine = CrossCheckEngine.__new__(CrossCheckEngine)
    items = [
        Contradiction(
            severity="high",
            claim_a="$72,000",
            claim_b="$72,000",
            source_doc_ids=["a"],
            confidence=0.8,
            quoted_evidence="x",
        ),
        Contradiction(
            severity="high",
            claim_a="Revenue $450,000",
            claim_b="Revenue $320,000",
            source_doc_ids=["a", "b"],
            confidence=0.9,
            quoted_evidence="y",
        ),
    ]
    out = CrossCheckEngine._filter_valid(engine, items)
    assert len(out) == 1
    assert "450" in out[0].claim_a
