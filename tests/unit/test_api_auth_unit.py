"""Backend unit: health + auth deps without Postgres."""

from __future__ import annotations

from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from apps.api.deps import RequireMutate, RequireRead, get_current_principal
from apps.api.routes import health
from packages.auth import Principal, principal_from_shared_api_key
from packages.config import get_settings
from packages.db.session import get_session


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_MODE", "both")
    monkeypatch.setenv("API_KEY", "unit-test-api-key")
    monkeypatch.setenv("OIDC_DEV_SECRET", "unit-test-oidc-secret-32-bytes-ok!")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _mini_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health.router)

    @app.get("/v1/secure-read")
    async def secure_read(principal: Principal = Depends(RequireRead)):
        return {"sub": principal.sub, "roles": sorted(principal.roles)}

    @app.post("/v1/secure-mutate")
    async def secure_mutate(principal: Principal = Depends(RequireMutate)):
        return {"ok": True, "sub": principal.sub}

    async def fake_session():
        session = AsyncMock()
        empty = AsyncMock()
        empty.scalar_one_or_none = lambda: None
        session.execute = AsyncMock(return_value=empty)
        yield session

    app.dependency_overrides[get_session] = fake_session
    return app


@pytest.mark.unit
def test_health_ok():
    app = FastAPI()
    app.include_router(health.router)
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.unit
def test_missing_bearer_401():
    client = TestClient(_mini_app())
    assert client.get("/v1/secure-read").status_code == 401


@pytest.mark.unit
def test_api_key_allows_mutate():
    app = _mini_app()
    client = TestClient(app)
    res = client.post(
        "/v1/secure-mutate",
        headers={"Authorization": "Bearer unit-test-api-key"},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True


@pytest.mark.unit
def test_reviewer_forbidden_on_mutate():
    app = _mini_app()

    async def _reviewer():
        return Principal(sub="r1", roles=["reviewer"], auth_method="oidc", tenant_id="bank-a")

    app.dependency_overrides[get_current_principal] = _reviewer
    client = TestClient(app)
    assert client.post("/v1/secure-mutate").status_code == 403
    assert client.get("/v1/secure-read").status_code == 200


@pytest.mark.unit
def test_oidc_bearer_read():
    app = _mini_app()
    secret = "unit-test-oidc-secret-32-bytes-ok!"
    token = jwt.encode(
        {"sub": "uw-1", "tenant_id": "bank-a", "roles": ["underwriter"]},
        secret,
        algorithm="HS256",
    )
    client = TestClient(app)
    res = client.get("/v1/secure-read", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["sub"] == "uw-1"


@pytest.mark.unit
def test_shared_key_principal_helper():
    p = principal_from_shared_api_key()
    assert "admin" in p.roles or p.has_any_role({"underwriter", "admin"})
