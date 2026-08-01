"""E2E: full investigation pipeline against Postgres (heuristic LLM + fixture OSINT)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "fixtures"


@pytest.fixture
async def db_session(require_postgres, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")
    monkeypatch.setenv("OSINT_MODE", "fixture")
    from packages.config import get_settings

    get_settings.cache_clear()

    from packages.db.session import _get_engine, init_db

    await init_db()
    _, factory = _get_engine()
    async with factory() as session:
        yield session
        await session.rollback()


async def _run_folder(session, vertical: str, folder: str, meta: dict):
    from packages.agent.investigation import InvestigationRunner
    from packages.db.models import CaseRecord
    from packages.documents.pipeline import DocumentPipeline
    from packages.policy_rag.service import PolicyRAGService

    # Seed policies once per session is fine
    policy = PolicyRAGService(session)
    for path in (FIXTURES / "policies").glob("*.md"):
        await policy.ingest_policy(
            "default",
            path.stem.replace("_", " ").title(),
            path.name,
            path.read_bytes(),
            "seed",
        )
    await session.commit()

    case_id = str(uuid.uuid4())
    case = CaseRecord(
        id=case_id,
        tenant_id="default",
        vertical=vertical,
        status="queued",
        metadata_json=meta,
    )
    session.add(case)
    await session.flush()

    pipeline = DocumentPipeline(session, case_id, "default")
    for f in sorted((FIXTURES / folder).glob("*.txt")):
        await pipeline.ingest_file(f.name, f.read_bytes())
    await session.commit()

    return await InvestigationRunner(session, case_id).run()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fraudulent_sba_flags_contradictions(db_session):
    cf = await _run_folder(
        db_session,
        "sba_7a",
        "sba/fraudulent",
        {
            "business_name": "Acme Consulting LLC",
            "employer": "Acme Consulting LLC",
            "stated_employer": "Acme Consulting LLC",
            "address": "1200 Market Street Suite 400 Wilmington DE",
            "annual_revenue": "450000",
        },
    )
    assert len(cf.contradictions) >= 1
    assert cf.recommended_action.value in ("review", "decline")
    assert cf.executive_summary
    assert "as Senior Operations Manager" not in " ".join(
        [cf.executive_summary] + list(cf.open_questions)
    )
    # Employer mismatch should surface in questions or findings
    blob = " ".join(cf.open_questions + [f.description for f in cf.findings]).lower()
    assert "employer" in blob or any("employer" in c.claim_a.lower() for c in cf.contradictions)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_clean_sba_completes(db_session):
    cf = await _run_folder(
        db_session,
        "sba_7a",
        "sba/clean",
        {
            "business_name": "Sunrise Bakery LLC",
            "employer": "Sunrise Bakery LLC",
            "stated_employer": "Sunrise Bakery LLC",
            "address": "88 Main Street Portland OR",
        },
    )
    assert cf.executive_summary
    assert cf.recommended_action.value in ("approve", "review")
    # Clean pack should not force decline
    assert cf.recommended_action.value != "decline"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_memo_render_after_investigation(db_session):
    from packages.memo import build_memo_context, render_memo

    cf = await _run_folder(
        db_session,
        "sba_7a",
        "sba/fraudulent",
        {
            "business_name": "Acme Consulting LLC",
            "stated_employer": "Acme Consulting LLC",
            "employer_from_letter": "Beta Industries Inc",
        },
    )
    ctx = build_memo_context(
        case_id="e2e",
        vertical="sba_7a",
        tenant_id="default",
        metadata={
            "employer": "Beta Industries Inc as Senior Operations Manager sinc",
            "stated_employer": "Acme Consulting LLC",
        },
        case_file=cf,
    )
    body = render_memo("sba_7a", ctx)
    assert "Executive summary" in body
    assert "as Senior Operations Manager" not in body
    assert "### High" in body or "Findings" in body
