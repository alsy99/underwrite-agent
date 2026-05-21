#!/usr/bin/env python3
"""
End-to-end local demo without Docker/Redis/MinIO.
Requires Postgres (with pgvector) — starts investigation inline.
"""

import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / "data" / "fixtures"


async def main() -> None:
    from packages.agent.investigation import InvestigationRunner
    from packages.db.models import CaseRecord
    from packages.db.session import _get_engine, init_db
    from packages.documents.pipeline import DocumentPipeline
    from packages.policy_rag.service import PolicyRAGService
    from packages.schemas.case import LoanVertical

    print("==> Initializing database...")
    await init_db()
    _, factory = _get_engine()

    async with factory() as session:
        tenant_id = "default"
        print("==> Seeding policies...")
        policy_service = PolicyRAGService(session)
        for path in (FIXTURES / "policies").glob("*.md"):
            await policy_service.ingest_policy(
                tenant_id, path.stem.replace("_", " ").title(), path.name, path.read_bytes(), "seed"
            )
        await session.commit()

        for label, folder in [("FRAUDULENT SBA", "sba/fraudulent"), ("CLEAN SBA", "sba/clean")]:
            print(f"\n{'='*60}\n==> Running case: {label}\n{'='*60}")
            case_id = str(uuid.uuid4())
            meta = {
                "business_name": "Acme Consulting LLC",
                "employer": "Acme Consulting LLC",
                "address": "1200 Market Street Suite 400 Wilmington DE",
                "stated_employer": "Acme Consulting LLC",
            }
            if "clean" in folder:
                meta = {
                    "business_name": "Sunrise Bakery LLC",
                    "employer": "Sunrise Bakery LLC",
                    "address": "88 Main Street Portland OR",
                    "stated_employer": "Sunrise Bakery LLC",
                }

            case = CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                vertical=LoanVertical.SBA_7A.value,
                status="queued",
                metadata_json=meta,
            )
            session.add(case)
            await session.flush()

            pipeline = DocumentPipeline(session, case_id, tenant_id)
            doc_dir = FIXTURES / folder
            for f in sorted(doc_dir.glob("*.txt")):
                print(f"  ingest: {f.name}")
                await pipeline.ingest_file(f.name, f.read_bytes())
            await session.commit()

            runner = InvestigationRunner(session, case_id)
            case_file = await runner.run()

            print(f"\n  Status: completed")
            print(f"  Recommended action: {case_file.recommended_action.value}")
            print(f"  Contradictions: {len(case_file.contradictions)}")
            for c in case_file.contradictions:
                print(f"    - [{c.severity}] {c.claim_a} | {c.claim_b}")
            print(f"  Policy findings: {len(case_file.policy_findings)}")
            for p in case_file.policy_findings:
                print(f"    - [{p.status}] {p.rule_ref}: {p.excerpt[:80]}...")
            print(f"  Findings: {len(case_file.findings)}")
            print(f"\n  Executive summary:\n  {case_file.executive_summary[:500]}...")
            print(f"\n  Open questions: {case_file.open_questions}")

        print("\n==> CRE fraudulent package")
        case_id = str(uuid.uuid4())
        case = CaseRecord(
            id=case_id,
            tenant_id=tenant_id,
            vertical=LoanVertical.CRE_ACQUISITION.value,
            status="queued",
            metadata_json={
                "business_name": "Oak Plaza Holdings LLC",
                "address": "200 Oak Street Dallas TX",
            },
        )
        session.add(case)
        await session.flush()
        pipeline = DocumentPipeline(session, case_id, tenant_id)
        for f in sorted((FIXTURES / "cre/fraudulent").glob("*.txt")):
            print(f"  ingest: {f.name}")
            await pipeline.ingest_file(f.name, f.read_bytes())
        await session.commit()
        case_file = await InvestigationRunner(session, case_id).run()
        print(f"  Contradictions: {len(case_file.contradictions)}")
        for c in case_file.contradictions:
            print(f"    - [{c.severity}] {c.claim_a}")

    print("\n==> All local E2E runs finished successfully.")


if __name__ == "__main__":
    asyncio.run(main())
