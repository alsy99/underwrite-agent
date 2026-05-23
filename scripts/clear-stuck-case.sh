#!/usr/bin/env bash
# Cancel or re-queue a case stuck in "queued" with no ARQ job.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=.

ACTION="${1:-}"
CASE_ID="${2:-}"

usage() {
  echo "Usage:"
  echo "  $0 list                          # show queued/processing cases"
  echo "  $0 cancel <case-id>              # mark failed + remove from Redis queue"
  echo "  $0 requeue <case-id>             # enqueue process_case again"
  exit 1
}

[[ -z "$ACTION" ]] && usage

python3.11 <<PY
import asyncio
import sys
from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select
from packages.config import get_settings
from packages.db.session import _get_engine
from packages.db.models import CaseRecord

action = "$ACTION"
case_id = "$CASE_ID"

async def list_cases():
    _, factory = _get_engine()
    async with factory() as session:
        rows = (
            await session.execute(
                select(CaseRecord)
                .where(CaseRecord.status.in_(("queued", "processing")))
                .order_by(CaseRecord.created_at.desc())
            )
        ).scalars().all()
    if not rows:
        print("No queued or processing cases.")
        return
    for c in rows:
        print(f"{c.id}  {c.status}  {c.created_at}")

async def cancel(cid: str):
    redis = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    _, factory = _get_engine()
    async with factory() as session:
        case = (
            await session.execute(select(CaseRecord).where(CaseRecord.id == cid))
        ).scalar_one_or_none()
        if not case:
            print(f"Case not found: {cid}")
            return
        case.status = "failed"
        case.error = "Cancelled — cleared from queue"
        from datetime import datetime, timezone
        case.completed_at = datetime.now(timezone.utc)
        await session.commit()
    # Best-effort: drain matching jobs (ARQ stores serialized jobs in sorted set)
    jobs = await redis.zrange("arq:queue", 0, -1)
    removed = 0
    for raw in jobs:
        if cid.encode() in raw if isinstance(raw, bytes) else cid in str(raw):
            await redis.zrem("arq:queue", raw)
            removed += 1
    await redis.aclose()
    print(f"Cancelled {cid} (removed {removed} redis job(s))")

async def requeue(cid: str):
    redis = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    job = await redis.enqueue_job("process_case", cid)
    await redis.aclose()
    print(f"Re-queued {cid} (job_id={job.job_id})")

async def main():
    if action == "list":
        await list_cases()
    elif action == "cancel":
        if not case_id:
            usage()
        await cancel(case_id)
    elif action == "requeue":
        if not case_id:
            usage()
        await requeue(case_id)
    else:
        usage()

asyncio.run(main())
PY
