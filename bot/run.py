import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from structlog.typing import FilteringBoundLogger

from env import settings
from handlers import register_handlers
from includes import PickleRedisStorage, get_fluent_localization, get_redis_storage, setup_logging
from includes.vpn import close_xui_client
from jobs import revoke_inactive_subscriptions, suspend_inactive_awg_access
from middlewares import register_middlewares


def _create_scheduler(bot: Bot) -> AsyncIOScheduler | None:
    """Планировщик фоновых задач. ``None``, если не настроены ни XUI, ни AmneziaWG."""
    if not settings.xui.ENABLED and not settings.awg.ENABLED:
        return None

    l10n = get_fluent_localization()
    # Оба отзыва - в одно время: сразу после синка членства.
    trigger = CronTrigger(
        hour=settings.xui.REVOKE_CRON_HOUR,
        minute=settings.xui.REVOKE_CRON_MINUTE,
        timezone=settings.xui.REVOKE_CRON_TIMEZONE,
    )
    scheduler = AsyncIOScheduler(timezone=settings.xui.REVOKE_CRON_TIMEZONE)
    if settings.xui.ENABLED:
        scheduler.add_job(
            revoke_inactive_subscriptions,
            trigger,
            args=(bot, l10n),
            id="revoke_inactive_vpn",
            replace_existing=True,
        )
    if settings.awg.ENABLED:
        scheduler.add_job(
            suspend_inactive_awg_access,
            trigger,
            args=(bot, l10n),
            id="suspend_inactive_awg",
            replace_existing=True,
        )
    return scheduler


async def main():
    # Init logging
    setup_logging()
    logger: FilteringBoundLogger = structlog.get_logger()

    # Init bot
    bot = Bot(
        token=settings.telegram.API_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2),
    )
    # Единственная команда: остальное - кнопки меню, доступные только мемберам.
    await bot.set_my_commands(
        [BotCommand(command="start", description="Профиль и меню")],
        scope=BotCommandScopeDefault(),
    )

    # Get storage with proper configuration for dialogs
    if settings.redis.USE_REDIS:
        storage = get_redis_storage(cls=PickleRedisStorage, with_destiny=True)
    else:
        storage = MemoryStorage()
        if not settings.project.DEBUG:
            await logger.aerror("You should use RedisStorage in production!")

    # Init dispatcher
    dp = Dispatcher(storage=storage)

    # Register handlers and middlewares
    register_middlewares(dp)
    register_handlers(dp)

    # Автоотзыв VPN-подписок у выбывших мемберов (без него ключи живут вечно)
    scheduler = _create_scheduler(bot)
    if scheduler is not None:
        scheduler.start()
        await logger.ainfo("VPN revoke jobs scheduled.", xui=settings.xui.ENABLED, awg=settings.awg.ENABLED)
    else:
        await logger.awarning("XUI and AWG settings are incomplete, VPN revoke jobs are disabled.")

    # Start bot
    await logger.ainfo(f"Starting the bot (id={bot.id})...")

    try:
        await dp.start_polling(
            bot,
            skip_updates=settings.project.DEBUG,  # skip updates if debug
            allowed_updates=dp.resolve_used_update_types(),  # Get only registered updates
        )
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        # Клиент AmneziaWG ходит через ту же сессию 3x-ui - закрывать его отдельно не нужно.
        await close_xui_client()
        await bot.session.close()
        await logger.ainfo("Bot stopped.")


# Start bot
if __name__ == "__main__":
    asyncio.run(main())
