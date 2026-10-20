"""Ежедневное отключение ключей AmneziaWG у выбывших мемберов.

Пару ``revoke_vpn`` для VLESS: пира в панели не удаляем, а выключаем, разрешение помечаем
``suspended``. Вернувшийся мембер получает тот же ключ по кнопке в боте, без участия админа.
Ошибки панели не роняют прогон - они уходят в сводку VP4HR.
"""

import structlog
from aiogram import Bot
from fluent.runtime import FluentLocalization
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.awg_access import list_accesses_to_suspend, mark_suspended
from includes.awg import AwgError, disable_peer, get_awg_client
from jobs.revoke_vpn import notify
from utils import escape_mdv2
from utils.board import get_hr_id

logger: FilteringBoundLogger = structlog.get_logger("awg-suspend")


async def suspend_inactive_awg_access(bot: Bot, l10n: FluentLocalization) -> None:
    client = get_awg_client()
    suspended: list[str] = []
    failed: list[str] = []

    async with async_session() as session:
        accesses = await list_accesses_to_suspend(session)

        for access in accesses:
            try:
                had_peer = await disable_peer(client, access)
            except AwgError as exc:
                failed.append(f"{access.client_name}: {exc}")
                await logger.aerror("awg-suspend-failed", client_name=access.client_name, error=str(exc))
                continue

            await mark_suspended(session, access)
            if not had_peer:
                # Конфиг так и не запрашивали (или пира снесли руками) - выключать нечего, молча чиним запись.
                await logger.ainfo("awg-suspend-peer-missing", client_name=access.client_name)
                continue

            suspended.append(access.client_name)
            await notify(bot, access.person.telegram_id, l10n.format_value("vpn-awg-suspended-notice"))

        await session.commit()

        hr_id = await get_hr_id(session)

    await logger.ainfo("awg-suspend-done", suspended=len(suspended), failed=len(failed))

    if not suspended and not failed:
        return

    report = l10n.format_value(
        "vpn-awg-suspend-report",
        args={
            "revoked": len(suspended),
            "failed": len(failed),
            "details": escape_mdv2("\n".join(suspended + failed)),
        },
    )
    await notify(bot, hr_id, report)
