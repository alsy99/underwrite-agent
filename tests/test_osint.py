"""OSINT suite + ToolRegistry tests."""

import os

import pytest

os.environ.setdefault("OSINT_MODE", "fixture")
os.environ.setdefault("LLM_PROVIDER", "heuristic")

from packages.config import get_settings
from packages.osint.corpus import names_match, normalize_key
from packages.osint.profile import ProfileAnalyzer
from packages.osint.providers.fixture import FixtureProvider, clear_fixture_cache
from packages.osint.providers.router import OsintRouter


@pytest.fixture(autouse=True)
def _osint_fixture_mode(monkeypatch):
    monkeypatch.setenv("OSINT_MODE", "fixture")
    get_settings.cache_clear()
    clear_fixture_cache()
    yield
    get_settings.cache_clear()
    clear_fixture_cache()


def test_normalize_key():
    assert normalize_key("Acme Consulting LLC") == "acme consulting llc"
    assert names_match("Acme Consulting LLC", "Acme Consulting")


@pytest.mark.asyncio
async def test_fixture_registry_match():
    fx = FixtureProvider()
    raw = fx.lookup_registry("Acme Consulting LLC", ein="12-3456789")
    assert raw["ok"]
    assert raw["data"]["status"] == "active"
    assert raw["data"]["registered_state"] == "DE"


@pytest.mark.asyncio
async def test_fixture_registry_not_found():
    fx = FixtureProvider()
    raw = fx.lookup_registry("Totally Fake Corp XYZ")
    assert raw["data"]["status"] == "not_found"


@pytest.mark.asyncio
async def test_employer_mismatch_acme_beta():
    fx = FixtureProvider()
    raw = fx.verify_employer("Beta Industries Inc", stated_employer="Acme Consulting LLC")
    assert raw["data"]["match"] is False
    assert raw["data"]["confidence"] < 0.5


@pytest.mark.asyncio
async def test_employer_match_same_entity():
    fx = FixtureProvider()
    raw = fx.verify_employer("Acme Consulting LLC", stated_employer="Acme Consulting LLC")
    assert raw["data"]["match"] is True


@pytest.mark.asyncio
async def test_sanctions_clear_and_hit():
    fx = FixtureProvider()
    clear = fx.check_sanctions("Acme Consulting LLC")
    assert clear["data"]["status"] == "clear"
    hit = fx.check_sanctions("Blocked Trader Syndicate")
    assert hit["data"]["status"] == "hit"


@pytest.mark.asyncio
async def test_router_fixture_mode():
    router = OsintRouter()
    assert router.mode == "fixture"
    out = router.unwrap(await router.lookup_registry("Sunrise Bakery LLC"))
    assert out["status"] == "active"
    assert out["mode"] == "fixture"


@pytest.mark.asyncio
async def test_address_ups_risk():
    fx = FixtureProvider()
    raw = fx.address_signals("The UPS Store 100 Mail Box Lane Suite 200 Las Vegas NV")
    assert raw["data"]["risk_level"] == "high"
    assert "virtual_office_ups_store" in raw["data"]["signals"]


def test_profile_analyzer_employer_mismatch_risk():
    analyzer = ProfileAnalyzer()
    profiles = analyzer.build_profiles(
        {
            "business_name": "Acme Consulting LLC",
            "employer": "Beta Industries Inc",
            "stated_employer": "Acme Consulting LLC",
            "applicant_name": "John Smith",
            "address": "1200 Market Street, Suite 400, Wilmington, DE 19801",
        },
        [
            {
                "tool": "lookup_business_registry",
                "result": {
                    "entity_name": "Acme Consulting LLC",
                    "status": "active",
                    "source": "fixture_corpus",
                },
            },
            {
                "tool": "verify_employer_osint",
                "result": {
                    "employer": "Beta Industries Inc",
                    "stated_employer": "Acme Consulting LLC",
                    "match": False,
                    "confidence": 0.2,
                    "source": "fixture_corpus",
                },
            },
            {
                "tool": "check_sanctions",
                "result": {"name": "Acme Consulting LLC", "status": "clear", "match": None},
            },
            {
                "tool": "address_risk_signals",
                "result": {
                    "address": "1200 Market Street",
                    "risk_level": "low",
                    "signals": [],
                },
            },
        ],
    )
    types = {p.entity_type for p in profiles}
    assert "business" in types
    assert "employer" in types
    employer = next(p for p in profiles if p.entity_type == "employer")
    assert employer.status == "mismatch"
    assert employer.risk_score >= 0.4


def test_case_file_builder_osint_findings():
    from packages.agent.case_file import CaseFileBuilder
    from packages.schemas.case import EntityProfile, OsintSignal, RecommendedAction

    builder = CaseFileBuilder()
    builder.set_entity_profiles(
        [
            EntityProfile(
                entity_name="Shell Holdings LLC",
                entity_type="business",
                identity_confidence=0.3,
                risk_score=0.7,
                status="flagged",
                signals=[
                    OsintSignal(
                        source="sanctions",
                        signal_type="sanctions_hit",
                        severity="high",
                        summary="Sanctions list hit",
                        confidence=0.95,
                    )
                ],
                sources_used=["fixture_corpus"],
            )
        ]
    )
    assert any(f.severity == "high" for f in builder.findings)
    assert builder.recommend_action() == RecommendedAction.REVIEW


@pytest.mark.asyncio
async def test_tool_registry_osint_dispatch():
    from packages.agent.tools.registry import ToolRegistry

    registry = ToolRegistry.__new__(ToolRegistry)
    registry.metadata = {
        "business_name": "Acme Consulting LLC",
        "stated_employer": "Acme Consulting LLC",
        "employer": "Beta Industries Inc",
        "address": "1200 Market Street, Suite 400, Wilmington, DE 19801",
    }
    registry.osint = OsintRouter()
    registry.profiler = ProfileAnalyzer()
    registry._geo_cache = {}
    registry._tool_results = []
    registry.settings = get_settings()

    emp = await registry.verify_employer_osint("Beta Industries Inc")
    assert emp["match"] is False

    reg = await registry.lookup_business_registry("Acme Consulting LLC")
    assert reg["status"] == "active"

    san = await registry.check_sanctions("Acme Consulting LLC")
    assert san["status"] == "clear"

    out = await registry.execute(
        "search_adverse_media",
        {"entity_name": "Beta Industries Inc"},
        "",
    )
    assert out["article_count"] >= 1


def test_metadata_enrichment_extracts_ein_and_applicant():
    from packages.agent.investigation import InvestigationRunner

    runner = InvestigationRunner.__new__(InvestigationRunner)
    meta = runner._enrich_metadata(
        {},
        """
        Business Legal Name: Acme Consulting LLC
        EIN: 12-3456789
        Business Address: 1200 Market Street, Suite 400, Wilmington, DE 19801
        Applicant Name: John Smith
        Stated Employer (for personal guarantee income): Acme Consulting LLC
        Website: https://acmeconsulting.example
        This letter confirms that John Smith is employed full-time by Beta Industries Inc
        """,
    )
    assert "Acme" in meta.get("business_name", "")
    assert meta.get("ein") == "12-3456789"
    assert meta.get("applicant_name") == "John Smith"
    assert meta.get("domain") == "acmeconsulting.example"
    # Letter employer wins when it conflicts with stated
    assert "Beta" in meta.get("employer", "")
