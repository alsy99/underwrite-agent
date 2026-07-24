from packages.agent.case_file import CaseFileBuilder
from packages.cross_check.engine import CrossCheckEngine
from packages.schemas.case import Contradiction, LoanVertical, PolicyFinding, RecommendedAction
from packages.verticals import get_vertical_pack


def test_specialty_mortgage_pack():
    pack = get_vertical_pack(LoanVertical.SPECIALTY_MORTGAGE)
    assert "bank_statement" in pack.required_doc_types
    assert "specialty_mortgage" in pack.policy_seed_path


def test_rule_based_bank_statement_income_mismatch():
    bundle = """
    [DOC type=application] Stated monthly income: $18,500
    Employer: Apex Design Studio LLC
    [DOC type=bank_statement] Average monthly deposits: $9,200
    Wire from CryptoExchange $6,800
    """
    engine = CrossCheckEngine.__new__(CrossCheckEngine)
    results = CrossCheckEngine._rule_based_checks(engine, bundle)
    assert any(r.severity == "high" for r in results)


def test_recommend_decline_on_compound_signals():
    builder = CaseFileBuilder()
    builder.add_contradictions(
        [
            Contradiction(
                severity="high",
                claim_a="income a",
                claim_b="income b",
                source_doc_ids=["application"],
                confidence=0.9,
                quoted_evidence="x",
            ),
            Contradiction(
                severity="high",
                claim_a="employer a",
                claim_b="employer b",
                source_doc_ids=["employment_letter"],
                confidence=0.9,
                quoted_evidence="y",
            ),
        ]
    )
    builder.add_policy_findings(
        [
            PolicyFinding(
                rule_ref="BSM-INC-001",
                status="fail",
                excerpt="income mismatch",
                source_policy_doc_id="policy",
                confidence=0.9,
            )
        ]
    )
    assert builder.recommend_action() == RecommendedAction.DECLINE


def test_metadata_enrichment_extracts_business_name():
    from packages.agent.investigation import InvestigationRunner

    runner = InvestigationRunner.__new__(InvestigationRunner)
    meta = runner._enrich_metadata(
        {},
        "Business name: Sunrise Bakery LLC\nAddress: 88 Main Street Portland OR\nEmployer: Sunrise Bakery LLC",
    )
    assert "Sunrise Bakery" in meta.get("business_name", "")
    assert meta.get("address")
    assert meta.get("employer") or meta.get("stated_employer")


def test_hash_embeddings_deterministic():
    import asyncio
    import os

    os.environ["LLM_PROVIDER"] = "heuristic"
    from packages.config import get_settings
    from packages.llm.embeddings import EmbeddingService

    get_settings.cache_clear()
    svc = EmbeddingService()

    async def _run():
        return await svc.embed(["hello world", "hello world"])

    a, b = asyncio.run(_run())
    assert a == b
    assert len(a) == EmbeddingService.DIMENSION


def test_graph_compiles():
    from apps.worker.agent_graph import GRAPH_STAGES, build_investigation_graph

    class Dummy:
        async def node_intake(self, state):
            return state

        async def node_cross_check(self, state):
            return state

        async def node_policy_rag(self, state):
            return state

        async def node_plan(self, state):
            return state

        async def node_agent_loop(self, state):
            return state

        async def node_synthesize(self, state):
            return state

        async def node_finalize(self, state):
            return state

    graph = build_investigation_graph(Dummy())
    assert graph is not None
    assert "plan_investigation" in GRAPH_STAGES
