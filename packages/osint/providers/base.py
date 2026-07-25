"""Normalized OSINT result helpers."""

from __future__ import annotations

from typing import Any, TypedDict


class ProviderResult(TypedDict, total=False):
    ok: bool
    source: str
    mode: str  # fixture|live
    data: dict[str, Any]
    error: str


def ok_result(source: str, mode: str, data: dict[str, Any]) -> ProviderResult:
    return {"ok": True, "source": source, "mode": mode, "data": data}


def err_result(source: str, mode: str, error: str) -> ProviderResult:
    return {"ok": False, "source": source, "mode": mode, "error": error, "data": {}}
