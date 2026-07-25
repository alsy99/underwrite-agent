from __future__ import annotations

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.auth import (
    ADMIN_ROLES,
    MUTATE_ROLES,
    READ_ROLES,
    Principal,
    principal_from_shared_api_key,
    principal_from_tenant_api_key,
    verify_oidc_jwt,
)
from packages.config import get_settings
from packages.db.session import get_session


async def get_current_principal(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty token")

    settings = get_settings()
    mode = (settings.auth_mode or "both").lower()

    # Shared env API key
    if mode in ("api_key", "both") and token == settings.api_key:
        return principal_from_shared_api_key()

    # Tenant-scoped API keys
    if mode in ("api_key", "both"):
        tenant_principal = await principal_from_tenant_api_key(session, token)
        if tenant_principal:
            return tenant_principal

    # OIDC JWT
    if mode in ("oidc", "both"):
        try:
            return verify_oidc_jwt(token)
        except jwt.InvalidTokenError as exc:
            if mode == "oidc":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid OIDC token: {exc}",
                ) from exc

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid Bearer token",
    )


# Back-compat alias for older Depends(verify_api_key)
async def verify_api_key(
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    return principal


def require_roles(*allowed: str):
    allowed_set = set(allowed)

    async def _dep(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not principal.has_any_role(allowed_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {sorted(allowed_set)}",
            )
        return principal

    return _dep


RequireMutate = require_roles(*MUTATE_ROLES)
RequireRead = require_roles(*READ_ROLES)
RequireAdmin = require_roles(*ADMIN_ROLES)


def resolve_tenant(principal: Principal, requested: str | None) -> str:
    """OIDC / tenant API keys own tenant; shared api_key may use request tenant."""
    if principal.auth_method in ("oidc", "tenant_api_key"):
        return principal.tenant_id
    return (requested or principal.tenant_id or "default").strip() or "default"
