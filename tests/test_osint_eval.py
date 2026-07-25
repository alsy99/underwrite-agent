"""CI floors for OSINT golden-set evaluation."""

import asyncio
import os
from pathlib import Path

import pytest

os.environ["OSINT_MODE"] = "fixture"
os.environ["LLM_PROVIDER"] = "heuristic"

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _fixture_mode(monkeypatch):
    monkeypatch.setenv("OSINT_MODE", "fixture")
    from packages.config import get_settings
    from packages.osint.providers.fixture import clear_fixture_cache

    get_settings.cache_clear()
    clear_fixture_cache()
    yield
    get_settings.cache_clear()
    clear_fixture_cache()


def test_osint_golden_eval_floors():
    from packages.osint.eval_runner import run_eval

    golden = ROOT / "data" / "evals" / "osint_golden.json"
    report = asyncio.run(run_eval(golden))

    assert report["case_pass_rate"] >= 0.85, report
    metrics = report["metrics"]
    assert metrics["has_employer_mismatch"]["f1"] >= 0.99
    assert metrics["has_sanctions_hit"]["f1"] >= 0.99
    assert metrics["address_high_risk"]["f1"] >= 0.99
    assert metrics["any_flagged_or_mismatch"]["f1"] >= 0.99
