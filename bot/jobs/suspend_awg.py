"""Ежедневное отключение ключей AmneziaWG у выбывших мемберов.

Пару ``revoke_vpn`` для VLESS: ключи устройств в панели не удаляем, а выключаем, разрешение
помечаем ``suspended``. Вернувшийся мембер включает те же ключи кнопкой в боте, без участия админа.
Ошибки панели и БД не роняют прогон - они уходят в сводку VP4HR.
"""

import structlog
from aiogram import Bot
from fluent.runtime import FluentLocalization
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.awg_access import list_accesses_to_suspend, mark_suspended
from includes.awg import AwgError, disable_peers, get_awg_client
from includes.notify import notify
from jobs.revoke_vpn import save_mark
from utils import escape_mdv2, split_message
from utils.board import get_hr_id

logger: FilteringBoundLogger = structlog.get_logger("awg-suspend")


async def suspend_inactive_awg_access(bot: Bot, l10n: FluentLocalization) -> None:
    client = get_awg_client()
    suspended: list[str] = []
    failed: list[str] = []

    async with async_session() as session:
        accesses = await list_accesses_to_suspend(session)
        hr_id = await get_hr_id(session)

    for access in accesses:
        name = f"{access.person.full_name} (tg {access.person.telegram_id})"
        try:
            found = await disable_peers(client, access)
            await save_mark(mark_suspended, access)
        except AwgError as exc:
            failed.append(f"{name}: {exc}")
            await logger.aerror("awg-suspend-failed", person_id=access.person_id, error=str(exc))
            continue
        except Exception as exc:
            # Сбой БД или ошибка в коде на одном человеке не должны оставить остальных с работающими ключами.
            error = {"who": name, "error": type(exc).__name__}
            failed.append(l10n.format_value("job-unexpected-error-part", args=error))
            await logger.aexception("awg-suspend-crashed", person_id=access.person_id)
            continue

        if not found:
            # Устройств не заводили (или ключи снесли руками) - выключать нечего, запись молча починили.
            await logger.ainfo("awg-suspend-no-peers", person_id=access.person_id)
            continue

        suspended.append(l10n.format_value("vpn-awg-suspend-line-part", args={"who": name, "count": found}))
        await notify(bot, access.person.telegram_id, l10n.format_value("vpn-awg-suspended-notice"))

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
    for part in split_message(report):
        await notify(bot, hr_id, part)
