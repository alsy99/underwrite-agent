import logging

from arq.connections import RedisSettings

from packages.config import get_settings
from packages.db.session import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def process_case(ctx: dict, case_id: str) -> None:
    from packages.agent.investigation import InvestigationRunner
    from packages.db.session import _get_engine

    _, factory = _get_engine()
    async with factory() as session:
        try:
            runner = InvestigationRunner(session, case_id)
            await runner.run()
            logger.info("Case %s investigation completed", case_id)
        except Exception as e:
            logger.exception("Case %s failed: %s", case_id, e)
            from sqlalchemy import select

            from packages.db.models import CaseRecord

            result = await session.execute(
                select(CaseRecord).where(CaseRecord.id == case_id)
            )
            case = result.scalar_one_or_none()
            if case:
                case.status = "failed"
                case.error = str(e)
                await session.commit()


async def startup(ctx: dict) -> None:
    await init_db()


class WorkerSettings:
    functions = [process_case]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    on_startup = startup


def main():
    from arq.worker import run_worker

    run_worker(WorkerSettings)


if __name__ == "__main__":
    main()
