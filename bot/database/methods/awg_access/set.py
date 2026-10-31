from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AwgAccess, AwgDevice


async def mark_granted(session: AsyncSession, access: AwgAccess) -> None:
    """Доступ снова в силе: админ выдал повторно или мембер вернулся. Коммит - на вызывающей стороне."""
    if access.status == "revoked":
        access.granted_at = datetime.now(UTC)
    access.status = "granted"
    access.disabled_at = None


async def mark_suspended(session: AsyncSession, access: AwgAccess) -> None:
    """Человек выбыл из LBG: ключи выключены, но вернутся сами вместе с членством."""
    access.status = "suspended"
    access.disabled_at = datetime.now(UTC)


async def mark_revoked(session: AsyncSession, access: AwgAccess) -> None:
    """Админ забрал доступ: окно AmneziaWG пропадает, ключи выключены до повторной выдачи."""
    access.status = "revoked"
    access.disabled_at = datetime.now(UTC)


async def mark_announced(session: AsyncSession, access: AwgAccess) -> None:
    """Рассылка о переезде AmneziaWG дошла до человека - повторный запуск его пропустит."""
    access.announced_at = datetime.now(UTC)


async def set_device_limit(session: AsyncSession, access: AwgAccess, device_limit: int | None) -> None:
    """Личный лимит устройств; ``None`` - лимит по умолчанию из настроек."""
    access.device_limit = device_limit


async def set_device_label(session: AsyncSession, device: AwgDevice, label: str | None) -> None:
    """Название устройства от владельца; ``None`` - «Устройство <number>»."""
    device.label = label


async def mark_issued(session: AsyncSession, device: AwgDevice) -> None:
    """Конфиг устройства отправлен человеку."""
    device.issued_at = datetime.now(UTC)


async def delete_device(session: AsyncSession, access: AwgAccess, device: AwgDevice) -> None:
    """Убрать устройство (пир в панели удаляет вызывающая сторона): номер освобождается."""
    access.devices.remove(device)
    await session.flush()
