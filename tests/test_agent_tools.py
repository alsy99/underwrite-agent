import pytest

from packages.agent.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_registry_stub_osint_mismatch():
    registry = ToolRegistry.__new__(ToolRegistry)
    registry.metadata = {"stated_employer": "Acme Consulting LLC"}

    async def verify(employer, profile_url=""):
        stated = registry.metadata.get("stated_employer", employer)
        match = stated.lower() in employer.lower()
        if "Beta" in employer and "Acme" in stated:
            match = False
        return {"employer": employer, "match": match}

    result = await verify("Beta Industries Inc")
    assert result["match"] is False


def test_case_file_recommend_review_on_high_contradiction():
    from packages.agent.case_file import CaseFileBuilder
    from packages.schemas.case import Contradiction, RecommendedAction

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
