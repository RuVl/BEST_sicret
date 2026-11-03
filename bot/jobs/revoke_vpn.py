"""Ежедневный отзыв VPN-подписок у выбывших мемберов.

Клиента в панели не удаляем, а выключаем (``enable=false``): статистика сохраняется,
а вернувшемуся мемберу подписка оживает по той же ссылке.

Ошибки панели и БД не роняют прогон целиком - они собираются и уходят в сводку VP4HR.
Сводка обязательна: без ``expiryTime`` на ключах этот джоб - единственный ограничитель
доступа, поэтому его молчаливая смерть должна быть заметна.
"""

from collections.abc import Awaitable, Callable

import structlog
from aiogram import Bot
from fluent.runtime import FluentLocalization
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.vpn_subscription import list_subscriptions_to_revoke, mark_revoked
from includes.notify import notify
from includes.vpn import XuiClient, XuiClientNotFoundError, XuiError, get_xui_client
from utils import escape_mdv2, split_message
from utils.board import get_hr_id

logger: FilteringBoundLogger = structlog.get_logger("vpn-revoke")


async def save_mark[Row](mark: Callable[[AsyncSession, Row], Awaitable[None]], row: Row) -> None:
    """Пометить строку прогона и сразу закоммитить - в своей сессии, отдельно от остальных людей.

    Коммит до уведомления: если он упадёт, человек не узнает об отключении, а следующей ночью джоб
    повторит его целиком - и уведомит один раз. Своя сессия - потому что откат общей сессии сбросил бы
    (expire) все загруженные строки прогона, и следующий человек упал бы на ленивой загрузке в async.
    """
    async with async_session() as session:
        session.add(row)
        await mark(session, row)
        await session.commit()


async def _disable_client(client: XuiClient, email: str) -> bool:
    """Выключить клиента в панели. ``False`` - его там уже нет (снесли в админке), выключать нечего."""
    try:
        await client.set_enabled(email, False)
    except XuiClientNotFoundError:
        return False
    return True


async def revoke_inactive_subscriptions(bot: Bot, l10n: FluentLocalization) -> None:
    client = get_xui_client()
    revoked: list[str] = []
    failed: list[str] = []

    async with async_session() as session:
        subscriptions = await list_subscriptions_to_revoke(session)
        hr_id = await get_hr_id(session)

    for subscription in subscriptions:
        email = subscription.xui_email
        try:
            found = await _disable_client(client, email)
            await save_mark(mark_revoked, subscription)
        except XuiError as exc:
            failed.append(f"{email}: {exc}")
            await logger.aerror("vpn-revoke-failed", email=email, error=str(exc))
            continue
        except Exception as exc:
            # Сбой БД или ошибка в коде на одном человеке не должны оставить остальных с работающим ключом.
            error = {"who": email, "error": type(exc).__name__}
            failed.append(l10n.format_value("job-unexpected-error-part", args=error))
            await logger.aexception("vpn-revoke-crashed", email=email)
            continue

        if not found:
            # Клиента уже снесли в админке - отзывать нечего, запись просто починили.
            await logger.ainfo("vpn-revoke-client-missing", email=email)
            continue

        revoked.append(email)
        await notify(bot, subscription.person.telegram_id, l10n.format_value("vpn-revoked-notice"))

    await logger.ainfo("vpn-revoke-done", revoked=len(revoked), failed=len(failed))

    if not revoked and not failed:
        return

    details = "\n".join(revoked + failed)
    report = l10n.format_value(
        "vpn-revoke-report",
        args={
            "revoked": len(revoked),
            "failed": len(failed),
            "details": escape_mdv2(details),
        },
    )
    # При массовом отзыве сводка длиннее лимита Telegram - шлём частями, иначе она не дойдёт вовсе.
    for part in split_message(report):
        await notify(bot, hr_id, part)
