"""Точка входа сервиса синхронизации участников.

RUN_MODE=once — один прогон и выход (для внешнего планировщика).
RUN_MODE=cron — контейнер живёт постоянно, запуск по расписанию (CRON_HOUR/MINUTE/TZ).
"""

import argparse
import asyncio

import structlog

from database.main import create_schema
from env import RunKeys, SyncKeys
from logger import setup_logging
from sync.service import run_sync

log = structlog.get_logger("members_sync")


async def _ensure_schema() -> None:
    if SyncKeys.AUTO_CREATE_SCHEMA:
        await create_schema()


async def _run_once(dry_run: bool = False) -> None:
    # В dry-run БД не трогаем — схему не создаём.
    if not dry_run:
        await _ensure_schema()
    await run_sync(dry_run=dry_run)


async def _run_cron() -> None:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    await _ensure_schema()

    # Первичный прогон при старте, чтобы не ждать до ближайшего расписания.
    await run_sync()

    scheduler = AsyncIOScheduler(timezone=RunKeys.CRON_TIMEZONE)
    scheduler.add_job(
        run_sync,
        CronTrigger(
            hour=RunKeys.CRON_HOUR,
            minute=RunKeys.CRON_MINUTE,
            timezone=RunKeys.CRON_TIMEZONE,
        ),
        id="daily_members_sync",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info(
        "Планировщик запущен",
        hour=RunKeys.CRON_HOUR,
        minute=RunKeys.CRON_MINUTE,
        tz=RunKeys.CRON_TIMEZONE,
    )

    stop = asyncio.Event()
    try:
        await stop.wait()  # держим процесс живым
    finally:
        scheduler.shutdown(wait=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="members_sync — синхронизация участников из Google Sheets")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Распарсить боевые данные и сохранить дамп в JSON, не записывая в БД (один прогон).",
    )
    args = parser.parse_args()

    setup_logging()

    if args.dry_run:
        log.info("members_sync старт", mode="dry-run")
        asyncio.run(_run_once(dry_run=True))
        return

    log.info("members_sync старт", mode=RunKeys.MODE)
    if RunKeys.MODE == "cron":
        asyncio.run(_run_cron())
    else:
        asyncio.run(_run_once())


if __name__ == "__main__":
    main()
