"""Ежедневный отзыв VPN-подписок у выбывших мемберов.

Клиента в панели не удаляем, а выключаем (``enable=false``): статистика сохраняется,
а вернувшемуся мемберу подписка оживает по той же ссылке.

Ошибки панели не роняют прогон целиком — они собираются и уходят в сводку VP4HR.
Сводка обязательна: без ``expiryTime`` на ключах этот джоб — единственный ограничитель
доступа, поэтому его молчаливая смерть должна быть заметна.
"""

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from fluent.runtime import FluentLocalization
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.vpn_subscription import list_subscriptions_to_revoke, mark_revoked
from includes.vpn import XuiClientNotFoundError, XuiError, get_xui_client
from utils import escape_mdv2
from utils.board import get_hr_id

logger: FilteringBoundLogger = structlog.get_logger("vpn-revoke")


async def _notify(bot: Bot, chat_id: int, text: str) -> None:
    """Уведомление не должно ронять джоб: человек мог заблокировать бота."""
    if not chat_id:
        return
    try:
        await bot.send_message(chat_id, text)
    except TelegramAPIError as exc:
        await logger.awarning("vpn-revoke-notify-failed", chat_id=chat_id, error=str(exc))


async def revoke_inactive_subscriptions(bot: Bot, l10n: FluentLocalization) -> None:
    client = get_xui_client()
    revoked: list[str] = []
    failed: list[str] = []

    async with async_session() as session:
        subscriptions = await list_subscriptions_to_revoke(session)

        for subscription in subscriptions:
            person = subscription.person
            try:
                await client.set_enabled(subscription.xui_email, False)
            except XuiClientNotFoundError:
                # Клиента уже снесли в админке — отзывать нечего, просто чиним запись.
                await mark_revoked(session, subscription)
                await logger.ainfo("vpn-revoke-client-missing", email=subscription.xui_email)
                continue
            except XuiError as exc:
                failed.append(f"{subscription.xui_email}: {exc}")
                await logger.aerror("vpn-revoke-failed", email=subscription.xui_email, error=str(exc))
                continue

            await mark_revoked(session, subscription)
            revoked.append(subscription.xui_email)
            await _notify(bot, person.telegram_id, l10n.format_value("vpn-revoked-notice"))

        await session.commit()

        hr_id = await get_hr_id(session)

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
    await _notify(bot, hr_id, report)
