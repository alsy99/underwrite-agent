#!/usr/bin/env python3
"""Seed policy documents for local development."""

import asyncio
from pathlib import Path

from packages.db.session import _get_engine, init_db
from packages.policy_rag.service import PolicyRAGService

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "policies"


async def main():
    await init_db()
    _, factory = _get_engine()
    async with factory() as session:
        service = PolicyRAGService(session)
        for path in FIXTURES.glob("*.md"):
            data = path.read_bytes()
            await service.ingest_policy(
                "default",
                path.stem.replace("_", " ").title(),
                path.name,
                data,
                policy_version="seed",
            )
            print(f"Ingested {path.name}")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
