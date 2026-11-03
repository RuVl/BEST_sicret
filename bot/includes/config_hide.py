"""Скрытие конфигов AmneziaWG из чата: удалить все сообщения, в которые ушёл приватный ключ.

Окно конфига показывает файл из памяти (``includes.memory_media``), каждая отправленная копия
попадает в реестр (``includes.pending_hides``), а скрытие удаляет их через Bot API напрямую - не
перерисовкой окна: перерисовка видит только последнее сообщение окна и не подтверждает удаление.

Запись в реестре снимается только когда все сообщения удалены (или Telegram окончательно не
даёт их удалить). Отмена таймера при остановке бота запись не трогает - её доберёт следующий старт.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

import structlog
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from structlog.typing import FilteringBoundLogger

from includes.memory_media import memory_media
from includes.pending_hides import PendingHide, get_pending_hides

logger: FilteringBoundLogger = structlog.get_logger("config-hide")

# Сообщения старше этого Telegram удалить не даёт - запись дольше держать бессмысленно.
_DELETE_WINDOW_SECONDS = 48 * 3600
# deleteMessages пропускает ненайденные сообщения сам; «нельзя удалить» - навсегда (старше 48 часов).
_FINAL_DELETE_ERRORS = ("message can't be deleted", "message to delete not found")
# Bot API удаляет не больше 100 сообщений за вызов.
_DELETE_BATCH = 100
# Повтор скрытия по таймеру, если Telegram временно не дал удалить: от минуты, удваивая, до часа.
_RETRY_FIRST_SECONDS = 60
_RETRY_MAX_SECONDS = 3600

Refresh = Callable[[], Awaitable[None]]

# Таймеры по токену: держим ссылки (иначе event loop может собрать задачу) и гасим по «Готово».
_timers: dict[str, asyncio.Task] = {}


async def track_config(token: str, user_id: int, chat_id: int, stack_id: str) -> None:
    """Завести запись до показа окна: первое же отправленное сообщение уже будет учтено."""
    await get_pending_hides().add(
        PendingHide(token=token, user_id=user_id, chat_id=chat_id, stack_id=stack_id, created_at=time.time())
    )


async def _on_media_sent(owner: str, chat_id: int, message_id: int) -> None:
    registry = get_pending_hides()
    if registry.get(owner) is None:
        # Владелец не конфиг (или его уже скрыли) - не наше сообщение.
        return
    await registry.add_message(owner, message_id)


def _is_final(exc: TelegramBadRequest) -> bool:
    text = exc.message.lower()
    return any(marker in text for marker in _FINAL_DELETE_ERRORS)


async def hide_config(bot: Bot, hide: PendingHide) -> bool:
    """Удалить все сообщения конфига. ``True`` - конфига в чате больше нет и запись снята."""
    registry = get_pending_hides()
    memory_media.drop_owned(hide.token)  # ключ в памяти бота больше не нужен ни при каком исходе

    messages = sorted(await registry.messages(hide.token))
    if not messages and hide.created_at == 0:
        # Запись прежнего формата (до учёта сообщений): что удалять, неизвестно - нужен человек.
        await logger.aerror("config-hide-legacy-record", chat_id=hide.chat_id, user_id=hide.user_id)

    pending = False
    for start in range(0, len(messages), _DELETE_BATCH):
        batch = messages[start : start + _DELETE_BATCH]
        try:
            await bot.delete_messages(hide.chat_id, batch)
        except TelegramBadRequest as exc:
            if not _is_final(exc):
                pending = True
                await logger.awarning("config-hide-delete-failed", chat_id=hide.chat_id, error=exc.message)
                continue
            await logger.ainfo("config-hide-already-gone", chat_id=hide.chat_id, error=exc.message)
        except TelegramAPIError as exc:
            # Сеть, RetryAfter, бот заблокирован: повторит таймер или следующий старт.
            pending = True
            await logger.awarning("config-hide-delete-failed", chat_id=hide.chat_id, error=str(exc))
            continue
        for message_id in batch:
            await registry.forget_message(hide.token, message_id)

    if pending and time.time() - hide.created_at < _DELETE_WINDOW_SECONDS:
        return False
    if pending:
        await logger.aerror("config-hide-given-up", chat_id=hide.chat_id, token=hide.token)

    await registry.remove(hide.token)
    memory_media.release_owner(hide.token)
    return True


async def _hide_later(bot: Bot, token: str, delay: float, refresh: Refresh | None) -> None:
    # CancelledError (остановка бота) пролетает мимо: запись остаётся для следующего старта.
    await asyncio.sleep(delay)
    retry = _RETRY_FIRST_SECONDS
    while (hide := get_pending_hides().get(token)) is not None:
        try:
            if await hide_config(bot, hide):
                if refresh is not None:
                    await refresh()
                return
        except Exception as exc:
            # Фоновая задача: исключение иначе ушло бы в «Task exception was never retrieved».
            await logger.aerror("config-hide-timer-failed", token=token, error=str(exc))
        # Telegram не дал удалить сейчас - пробуем ещё, пока не удалим или не выйдет окно в 48 часов.
        await asyncio.sleep(retry)
        retry = min(retry * 2, _RETRY_MAX_SECONDS)


def schedule_hide(bot: Bot, token: str, delay: float, refresh: Refresh | None = None) -> None:
    """Скрыть конфиг через ``delay`` секунд. ``refresh`` - перерисовать окно после удаления."""
    cancel_timer(token)
    task = asyncio.create_task(_hide_later(bot, token, delay, refresh))
    _timers[token] = task
    task.add_done_callback(lambda done: _timers.pop(token, None) if _timers.get(token) is done else None)


def cancel_timer(token: str) -> None:
    task = _timers.pop(token, None)
    if task is not None:
        task.cancel()


async def hide_now(bot: Bot, token: str) -> bool:
    """Скрыть сразу (человек нажал «Готово» или открыл другой конфиг) и погасить таймер."""
    cancel_timer(token)
    hide = get_pending_hides().get(token)
    if hide is None:
        return True
    return await hide_config(bot, hide)


async def hide_leftover_configs(bot: Bot) -> None:
    """При старте: скрыть конфиги, которые не успели скрыть до остановки. Срок ждать незачем -
    байтов конфига в памяти уже нет, показать файл заново окно всё равно не сможет."""
    hides = await get_pending_hides().load_all()
    hidden = 0
    for hide in hides:
        hidden += await hide_config(bot, hide)
    if hides:
        await logger.ainfo("config-hide-leftovers", total=len(hides), hidden=hidden)


def setup_config_hides(dp: Dispatcher) -> None:
    """Подписать реестр на отправку медиа и добрать оставшиеся конфиги на старте polling'а."""
    memory_media.set_sent_listener(_on_media_sent)
    dp.startup.register(hide_leftover_configs)
