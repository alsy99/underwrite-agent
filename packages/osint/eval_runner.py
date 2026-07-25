"""OSINT golden-set evaluation (fixture mode)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.config import get_settings
from packages.osint.profile import ProfileAnalyzer
from packages.osint.providers.fixture import clear_fixture_cache
from packages.osint.providers.router import OsintRouter


async def tool_results_for(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    get_settings.cache_clear()
    router = OsintRouter()
    business = metadata.get("business_name") or ""
    employer = metadata.get("employer") or metadata.get("stated_employer") or ""
    stated = metadata.get("stated_employer") or employer
    address = metadata.get("address") or ""
    applicant = metadata.get("applicant_name") or ""

    results: list[dict[str, Any]] = []

    async def add(tool: str, raw: Any) -> None:
        if isinstance(raw, dict) and "ok" in raw:
            results.append({"tool": tool, "args": {}, "result": router.unwrap(raw)})
        else:
            results.append({"tool": tool, "args": {}, "result": raw})

    if business:
        await add(
            "lookup_business_registry",
            await router.lookup_registry(business, metadata.get("ein", "")),
        )
        await add(
            "verify_web_presence",
            await router.web_presence(business, metadata.get("domain", "")),
        )
        await add("check_sanctions", await router.check_sanctions(business))
        await add("search_adverse_media", await router.adverse_media(business))
        await add("lookup_sec_filings", await router.sec_filings(business))
    if employer:
        await add(
            "verify_employer_osint",
            await router.verify_employer(employer, stated),
        )
    if address:
        await add("address_risk_signals", await router.address_signals(address))
        await add(
            "geocode_address",
            {
                "ok": True,
                "source": "eval_stub",
                "mode": "fixture",
                "data": {
                    "address": address,
                    "lat": "0",
                    "lon": "0",
                    "source": "eval_stub",
                },
            },
        )
    if applicant and applicant.lower() != (business or "").lower():
        await add("check_sanctions", await router.check_sanctions(applicant))

    return results


def predict(profiles: list) -> dict[str, Any]:
    by_type = {p.entity_type: p for p in profiles}
    business = by_type.get("business")
    employer = by_type.get("employer")
    address = by_type.get("address")
    signals = [s for p in profiles for s in p.signals]

    return {
        "business_status": business.status if business else None,
        "employer_status": employer.status if employer else None,
        "address_status": address.status if address else None,
        "has_employer_mismatch": any(s.signal_type == "employer_mismatch" for s in signals),
        "has_sanctions_hit": any(
            s.signal_type in ("sanctions_hit", "principal_sanctions") and s.severity == "high"
            for s in signals
        )
        or any((p.sanctions or {}).get("status") == "hit" for p in profiles if p.sanctions),
        "has_sanctions_possible_or_hit": any(s.signal_type.startswith("sanctions") for s in signals)
        or any(
            (p.sanctions or {}).get("status") in ("hit", "possible_match")
            for p in profiles
            if p.sanctions
        ),
        "address_high_risk": bool(
            address
            and (
                (address.address or {}).get("risk_level") == "high"
                or address.risk_score >= 0.35
                or any(
                    s.source == "address_risk" and s.severity == "high" for s in address.signals
                )
            )
        ),
        "has_adverse_media": any(s.signal_type == "adverse_media" for s in signals)
        or any(bool(p.adverse_media) for p in profiles),
        "any_flagged_or_mismatch": any(p.status in ("flagged", "mismatch") for p in profiles),
    }


def check_case(expect: dict[str, Any], pred: dict[str, Any]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    if "business_status_in" in expect:
        checks["business_status"] = pred["business_status"] in expect["business_status_in"]
    if "employer_status_in" in expect:
        checks["employer_status"] = pred["employer_status"] in expect["employer_status_in"]
    for key in (
        "has_employer_mismatch",
        "has_sanctions_hit",
        "has_sanctions_possible_or_hit",
        "address_high_risk",
        "has_adverse_media",
        "any_flagged_or_mismatch",
    ):
        if key in expect:
            checks[key] = bool(pred.get(key)) == bool(expect[key])
    return checks


def prf(y_true: list[bool], y_pred: list[bool]) -> dict[str, float]:
    tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t and not p)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "support": sum(y_true),
    }


async def run_eval(golden_path: Path) -> dict[str, Any]:
    get_settings.cache_clear()
    clear_fixture_cache()

    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    analyzer = ProfileAnalyzer()
    case_rows = []

    metric_keys = [
        "has_employer_mismatch",
        "has_sanctions_hit",
        "address_high_risk",
        "any_flagged_or_mismatch",
    ]
    buckets: dict[str, tuple[list[bool], list[bool]]] = {k: ([], []) for k in metric_keys}

    for case in golden["cases"]:
        meta = case["metadata"]
        tools = await tool_results_for(meta)
        profiles = analyzer.build_profiles(meta, tools)
        pred = predict(profiles)
        checks = check_case(case["expect"], pred)
        case_rows.append(
            {
                "id": case["id"],
                "passed": all(checks.values()) if checks else True,
                "checks": checks,
                "predicted": pred,
                "profile_statuses": {p.entity_type: p.status for p in profiles},
            }
        )
        for key in metric_keys:
            if key not in case["expect"]:
                continue
            buckets[key][0].append(bool(case["expect"][key]))
            buckets[key][1].append(bool(pred[key]))

    metrics = {k: prf(yt, yp) for k, (yt, yp) in buckets.items() if yt}
    case_pass = sum(1 for r in case_rows if r["passed"])
    return {
        "golden_version": golden.get("version"),
        "n_cases": len(case_rows),
        "case_pass_rate": round(case_pass / len(case_rows), 4) if case_rows else 0.0,
        "cases_passed": case_pass,
        "metrics": metrics,
        "cases": case_rows,
        "disclaimer": (
            "Metrics are on a synthetic fixture corpus only — not production portfolios."
        ),
    }
