"""Auth / SSO unit tests (HS256 OIDC_DEV_SECRET)."""

import jwt
import pytest

from packages.auth import (
    MUTATE_ROLES,
    Principal,
    hash_api_key,
    principal_from_shared_api_key,
    verify_oidc_jwt,
)
from packages.config import get_settings


@pytest.fixture(autouse=True)
def _auth_settings(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "both")
    monkeypatch.setenv("OIDC_DEV_SECRET", "test-secret-at-least-32-bytes-long!!")
    monkeypatch.setenv("API_KEY", "dev-api-key-change-me")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_shared_api_key_principal_has_admin():
    p = principal_from_shared_api_key()
    assert p.has_any_role(MUTATE_ROLES)
    assert p.auth_method == "api_key"


def test_oidc_hs256_jwt():
    token = jwt.encode(
        {
            "sub": "user-1",
            "email": "uw@bank.test",
            "tenant_id": "bank-a",
            "roles": ["underwriter"],
        },
        "test-secret-at-least-32-bytes-long!!",
        algorithm="HS256",
    )
    p = verify_oidc_jwt(token)
    assert p.sub == "user-1"
    assert p.tenant_id == "bank-a"
    assert p.has_any_role({"underwriter"})


def test_oidc_invalid_token():
    with pytest.raises(Exception):
        verify_oidc_jwt("not-a-jwt")


def test_reviewer_lacks_mutate_role():
    principal = Principal(sub="r", roles=["reviewer"], auth_method="oidc")
    assert not principal.has_any_role(MUTATE_ROLES)

def test_hash_api_key_stable():
    assert hash_api_key("abc") == hash_api_key("abc")
    assert hash_api_key("abc") != hash_api_key("abd")


def test_resolve_tenant_oidc_ignores_request():
    from apps.api.deps import resolve_tenant

    p = Principal(sub="u", tenant_id="bank-a", auth_method="oidc", roles=["underwriter"])
    assert resolve_tenant(p, "other") == "bank-a"
    p2 = Principal(sub="api_key", tenant_id="default", auth_method="api_key", roles=["admin"])
    assert resolve_tenant(p2, "demo") == "demo"
