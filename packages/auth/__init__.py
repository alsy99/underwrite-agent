"""Authentication principals and OIDC / API-key verification."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import jwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.config import get_settings
from packages.db.models import ApiKeyRecord

ROLE_ADMIN = "admin"
ROLE_UNDERWRITER = "underwriter"
ROLE_REVIEWER = "reviewer"

MUTATE_ROLES = {ROLE_ADMIN, ROLE_UNDERWRITER}
READ_ROLES = {ROLE_ADMIN, ROLE_UNDERWRITER, ROLE_REVIEWER}
ADMIN_ROLES = {ROLE_ADMIN}

__all__ = [
    "Principal",
    "ROLE_ADMIN",
    "ROLE_UNDERWRITER",
    "ROLE_REVIEWER",
    "MUTATE_ROLES",
    "READ_ROLES",
    "ADMIN_ROLES",
    "hash_api_key",
    "verify_oidc_jwt",
    "principal_from_shared_api_key",
    "principal_from_tenant_api_key",
]


@dataclass
class Principal:
    sub: str
    email: str = ""
    tenant_id: str = "default"
    roles: list[str] = field(default_factory=list)
    auth_method: str = "api_key"  # api_key | oidc | tenant_api_key

    def has_any_role(self, allowed: set[str]) -> bool:
        return bool(set(self.roles) & allowed)

    @property
    def actor(self) -> str:
        return self.email or self.sub


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _roles_from_claim(raw: Any) -> list[str]:
    if raw is None:
        return [ROLE_UNDERWRITER]
    if isinstance(raw, str):
        return [r.strip() for r in raw.split(",") if r.strip()]
    if isinstance(raw, list):
        return [str(r) for r in raw]
    return [ROLE_UNDERWRITER]


_jwks_clients: dict[str, PyJWKClient] = {}


def _jwks_client(url: str) -> PyJWKClient:
    if url not in _jwks_clients:
        _jwks_clients[url] = PyJWKClient(url, cache_keys=True)
    return _jwks_clients[url]


def _principal_from_claims(payload: dict[str, Any], auth_method: str) -> Principal:
    settings = get_settings()
    tenant_claim = settings.oidc_tenant_claim
    roles_claim = settings.oidc_roles_claim
    tenant = str(payload.get(tenant_claim) or payload.get("org_id") or "default")
    roles = _roles_from_claim(payload.get(roles_claim))
    return Principal(
        sub=str(payload.get("sub") or "unknown"),
        email=str(payload.get("email") or ""),
        tenant_id=tenant,
        roles=roles,
        auth_method=auth_method,
    )


def verify_oidc_jwt(token: str) -> Principal:
    settings = get_settings()
    options = {"verify_aud": bool(settings.oidc_audience)}

    # Local/CI: HS256 with shared secret
    if settings.oidc_dev_secret:
        try:
            payload = jwt.decode(
                token,
                settings.oidc_dev_secret,
                algorithms=["HS256"],
                audience=settings.oidc_audience or None,
                options={**options, "verify_aud": bool(settings.oidc_audience)},
            )
            return _principal_from_claims(payload, auth_method="oidc")
        except jwt.InvalidTokenError:
            if not settings.oidc_jwks_url and not settings.oidc_issuer:
                raise

    jwks_url = settings.oidc_jwks_url
    if not jwks_url and settings.oidc_issuer:
        jwks_url = settings.oidc_issuer.rstrip("/") + "/.well-known/jwks.json"
    if not jwks_url:
        raise jwt.InvalidTokenError("OIDC JWKS not configured")

    client = _jwks_client(jwks_url)
    signing_key = client.get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        audience=settings.oidc_audience or None,
        issuer=settings.oidc_issuer or None,
        options=options,
    )
    return _principal_from_claims(payload, auth_method="oidc")


def principal_from_shared_api_key() -> Principal:
    settings = get_settings()
    roles = _roles_from_claim(settings.api_key_default_roles)
    return Principal(
        sub="api_key",
        email="",
        tenant_id=settings.api_key_default_tenant,
        roles=roles,
        auth_method="api_key",
    )


async def principal_from_tenant_api_key(
    session: AsyncSession, raw_key: str
) -> Principal | None:
    digest = hash_api_key(raw_key)
    result = await session.execute(
        select(ApiKeyRecord).where(
            ApiKeyRecord.key_hash == digest, ApiKeyRecord.active.is_(True)
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    roles = list(row.roles_json or [ROLE_UNDERWRITER])
    return Principal(
        sub=f"api_key:{row.id}",
        email="",
        tenant_id=row.tenant_id,
        roles=roles,
        auth_method="tenant_api_key",
    )
