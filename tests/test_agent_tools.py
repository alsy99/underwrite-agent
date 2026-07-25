"""Legacy agent tool tests (compat) + case file recommendation."""

from packages.agent.case_file import CaseFileBuilder
from packages.schemas.case import Contradiction, RecommendedAction


def test_case_file_recommend_review_on_high_contradiction():
    builder = CaseFileBuilder()
    builder.add_contradictions(
        [
            Contradiction(
                severity="high",
                claim_a="a",
                claim_b="b",
                source_doc_ids=["d1"],
                confidence=0.9,
                quoted_evidence="x",
            )
        ]
    )
    assert builder.recommend_action() == RecommendedAction.REVIEW
