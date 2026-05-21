#!/usr/bin/env python3
"""Fast happy-path: clean SBA package, sync investigation (no Ollama — ~5s)."""

import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Skip slow LLM round-trips for demo happy path
os.environ["LLM_PROVIDER"] = "heuristic"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / "data" / "fixtures" / "sba" / "clean"
OUT = ROOT / "output"


async def main():
    from packages.config import get_settings

    get_settings.cache_clear()
    from packages.agent.investigation import InvestigationRunner
    from packages.db.models import CaseRecord
    from packages.db.session import _get_engine, init_db
    from packages.documents.pipeline import DocumentPipeline
    from packages.policy_rag.service import PolicyRAGService
    from packages.schemas.case import LoanVertical

    await init_db()
    _, factory = _get_engine()
    case_id = str(uuid.uuid4())
    tenant_id = "default"
    meta = {
        "business_name": "Sunrise Bakery LLC",
        "employer": "Sunrise Bakery LLC",
        "address": "88 Main Street Portland OR",
        "stated_employer": "Sunrise Bakery LLC",
    }

    async with factory() as session:
        policy = PolicyRAGService(session)
        seed = ROOT / "data" / "fixtures" / "policies" / "sba_policy_seed.md"
        await policy.ingest_policy(tenant_id, "SBA Policy", seed.name, seed.read_bytes(), "seed")

        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                vertical=LoanVertical.SBA_7A.value,
                status="queued",
                metadata_json=meta,
            )
        )
        await session.flush()

        pipe = DocumentPipeline(session, case_id, tenant_id)
        for f in sorted(FIXTURES.glob("*.txt")):
            await pipe.ingest_file(f.name, f.read_bytes())
        await session.commit()

        cf = await InvestigationRunner(session, case_id).run()

    OUT.mkdir(exist_ok=True)
    path = OUT / "happy_flow_case_file.json"
    path.write_text(json.dumps(cf.model_dump(mode="json"), indent=2))

    md = OUT / "happy_flow_report.md"
    md.write_text(
        f"""# Happy Flow — Clean SBA Package

| Field | Value |
|-------|-------|
| Case ID | `{case_id}` |
| Recommended action | **{cf.recommended_action.value.upper()}** |
| Contradictions | {len(cf.contradictions)} |
| Policy findings | {len(cf.policy_findings)} |
| Findings | {len(cf.findings)} |

## Summary

{cf.executive_summary[:800]}

## Contradictions

{chr(10).join(f"- [{c.severity}] {c.claim_a} vs {c.claim_b}" for c in cf.contradictions) or "_None_"}

## Open questions

{chr(10).join(f"- {q}" for q in cf.open_questions) or "_None_"}
"""
    )

    print(f"CASE_ID={case_id}")
    print(f"ACTION={cf.recommended_action.value}")
    print(f"CONTRADICTIONS={len(cf.contradictions)}")
    print(f"REPORT={md}")
    print(f"JSON={path}")


if __name__ == "__main__":
    asyncio.run(main())
