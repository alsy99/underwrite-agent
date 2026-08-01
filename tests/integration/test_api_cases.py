"""API integration tests against real Postgres (skip if unreachable)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "fixtures"


@pytest.fixture
async def api_client(require_postgres, monkeypatch):
    monkeypatch.setenv("API_KEY", "dev-api-key-change-me")
    monkeypatch.setenv("AUTH_MODE", "both")
    monkeypatch.setenv("SYNC_INVESTIGATION", "0")
    monkeypatch.setenv("LLM_PROVIDER", "heuristic")
    monkeypatch.setenv("OSINT_MODE", "fixture")
    from packages.config import get_settings

    get_settings.cache_clear()

    from apps.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer dev-api-key-change-me"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_via_app(api_client: AsyncClient):
    res = await api_client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "underwrite-agent"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cases_require_auth(api_client: AsyncClient):
    res = await api_client.get("/v1/cases")
    assert res.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_vertical_400(api_client: AsyncClient):
    res = await api_client.post(
        "/v1/cases",
        headers=_auth(),
        data={"vertical": "not_a_real_vertical", "tenant_id": "default", "metadata": "{}"},
    )
    assert res.status_code == 400
    assert "Invalid vertical" in res.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_metadata_json_400(api_client: AsyncClient):
    res = await api_client.post(
        "/v1/cases",
        headers=_auth(),
        data={"vertical": "sba_7a", "tenant_id": "default", "metadata": "{not-json"},
    )
    assert res.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_and_list_case(api_client: AsyncClient):
    doc = FIXTURES / "sba" / "clean" / "form_1919.txt"
    files = [("documents", (doc.name, doc.read_bytes(), "text/plain"))]
    res = await api_client.post(
        "/v1/cases",
        headers=_auth(),
        data={
            "vertical": "sba_7a",
            "tenant_id": "default",
            "metadata": '{"business_name":"Sunrise Bakery LLC"}',
        },
        files=files,
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["case_id"]
    assert body["status"] in ("queued", "processing", "completed")

    listed = await api_client.get(
        "/v1/cases",
        headers=_auth(),
        params={"tenant_id": "default", "limit": 50},
    )
    assert listed.status_code == 200
    ids = {c["case_id"] for c in listed.json()}
    assert body["case_id"] in ids

    detail = await api_client.get(f"/v1/cases/{body['case_id']}", headers=_auth())
    assert detail.status_code == 200
    assert detail.json()["vertical"] == "sba_7a"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_policy_json_ingest(api_client: AsyncClient):
    res = await api_client.post(
        "/v1/tenants/default/policies/json",
        headers={**_auth(), "Content-Type": "application/json"},
        json={
            "title": "Integration Policy Seed",
            "policy_version": "test.1",
            "filename": "integration_policy.md",
            "content": "# Policy\n\nEmployer names must match verification letters.\n",
        },
    )
    assert res.status_code in (200, 201), res.text
    listed = await api_client.get("/v1/tenants/default/policies", headers=_auth())
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)
