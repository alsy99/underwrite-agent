#!/usr/bin/env python3
"""API integration tests against mock fixtures (polls until complete)."""

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"
API = "http://127.0.0.1:8000"
KEY = "dev-api-key-change-me"
HEADERS = {"Authorization": f"Bearer {KEY}"}
TIMEOUT = 180


def submit_case(name: str, vertical: str, folder: Path, metadata: dict) -> str:
    files = [
        ("documents", (p.name, p.read_bytes(), "text/plain"))
        for p in sorted(folder.glob("*.txt"))
    ]
    data = {
        "vertical": vertical,
        "tenant_id": "default",
        "metadata": json.dumps(metadata),
    }
    with httpx.Client(timeout=120.0) as client:
        r = client.post(f"{API}/v1/cases", headers=HEADERS, data=data, files=files)
        r.raise_for_status()
        body = r.json()
        print(f"  created {name}: {body['case_id']} ({body['status']})")
        return body["case_id"]


def wait_case(case_id: str) -> dict:
    with httpx.Client(timeout=30.0) as client:
        for i in range(60):
            r = client.get(f"{API}/v1/cases/{case_id}", headers=HEADERS)
            r.raise_for_status()
            body = r.json()
            status = body["status"]
            if i % 5 == 0:
                print(f"    poll {i}: {status}")
            if status in ("completed", "failed"):
                return body
            time.sleep(3)
    raise TimeoutError(f"Case {case_id} did not complete in time")


def assert_case(
    name: str,
    body: dict,
    *,
    min_contradictions: int,
    max_contradictions: int | None = None,
    max_high_severity: int | None = None,
):
    assert body["status"] == "completed", f"{name}: expected completed, got {body['status']} error={body.get('error')}"
    cf = body.get("case_file") or {}
    contradictions = cf.get("contradictions") or []
    n = len(contradictions)
    assert n >= min_contradictions, f"{name}: expected >= {min_contradictions} contradictions, got {n}"
    if max_contradictions is not None:
        assert n <= max_contradictions, f"{name}: expected <= {max_contradictions} contradictions, got {n}"
    if max_high_severity is not None:
        high = sum(1 for c in contradictions if c.get("severity") == "high")
        assert high <= max_high_severity, f"{name}: expected <= {max_high_severity} high-severity, got {high}"
    summary = cf.get("executive_summary") or ""
    assert "Heuristic mode" not in summary, f"{name}: fell back to heuristic (check OLLAMA_MODEL)"
    print(f"  PASS {name}: action={cf.get('recommended_action')} contradictions={n} policy={len(cf.get('policy_findings') or [])}")
    print(f"    summary: {summary[:120].replace(chr(10), ' ')}...")


def main() -> int:
    print("==> Health")
    with httpx.Client() as client:
        h = client.get(f"{API}/health")
        h.raise_for_status()
        print(f"  {h.json()}")

    print("==> Policy upload")
    with httpx.Client(timeout=60.0) as client:
        policy = FIXTURES / "policies" / "sba_policy_seed.md"
        r = client.post(
            f"{API}/v1/tenants/default/policies",
            headers=HEADERS,
            data={"title": "SBA Policy Test", "policy_version": "test"},
            files={"file": (policy.name, policy.read_bytes(), "text/markdown")},
        )
        r.raise_for_status()
        print(f"  uploaded policy {r.json()['id']}")

    cases = [
        (
            "fraudulent_sba",
            "sba_7a",
            FIXTURES / "sba" / "fraudulent",
            {
                "business_name": "Acme Consulting LLC",
                "employer": "Acme Consulting LLC",
                "address": "1200 Market Street Suite 400 Wilmington DE",
                "stated_employer": "Acme Consulting LLC",
            },
            1,
            None,
        ),
        (
            "clean_sba",
            "sba_7a",
            FIXTURES / "sba" / "clean",
            {
                "business_name": "Sunrise Bakery LLC",
                "employer": "Sunrise Bakery LLC",
                "address": "88 Main Street Portland OR",
                "stated_employer": "Sunrise Bakery LLC",
            },
            0,
            1,  # allow low-severity LLM noise; no high-severity fraud expected
        ),
        (
            "fraudulent_cre",
            "cre_acquisition",
            FIXTURES / "cre" / "fraudulent",
            {
                "business_name": "Oak Plaza Holdings LLC",
                "address": "200 Oak Street Dallas TX",
            },
            1,
            None,
        ),
    ]

    extra = {"clean_sba": {"max_high_severity": 0}}

    for name, vertical, folder, meta, min_c, max_c in cases:
        print(f"\n==> Case: {name}")
        case_id = submit_case(name, vertical, folder, meta)
        result = wait_case(case_id)
        opts = extra.get(name, {})
        assert_case(
            name,
            result,
            min_contradictions=min_c,
            max_contradictions=max_c,
            max_high_severity=opts.get("max_high_severity"),
        )

        with httpx.Client() as client:
            audit = client.get(f"{API}/v1/cases/{case_id}/audit", headers=HEADERS)
            audit.raise_for_status()
            events = audit.json()
            assert len(events) >= 3, f"{name}: expected audit events, got {len(events)}"
            print(f"  audit events: {len(events)}")

    print("\n==> All API integration tests passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        raise SystemExit(1) from e
