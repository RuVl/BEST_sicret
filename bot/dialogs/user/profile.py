"""Диалог ``/profile``: карточка мембера и вход в VPN-подписку.

Данные о человеке - readonly-слепок из гугл-таблицы (``LbgMember``, синхронизируется
members_sync). Не опознанным пользователям показываем приветствие с приглашением вступить.
"""

from typing import Any

from aiogram import F
from aiogram_dialog import Dialog, DialogManager, LaunchMode, Window
from aiogram_dialog.widgets.kbd import Cancel, Start
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization

from database.main import async_session
from database.methods.person import get_or_create_person
from state_machines.profile import ViewProfile
from state_machines.vpn import ViewVpnSubscription
from utils import L10nFormat, escape_mdv2, truncate

FIELD_TRUNCATE_LEN = 200

# Человекочитаемые названия категорий членства (значения проставляет members_sync).
_CATEGORY_NAMES = {
    "board": "BOARD",
    "full_member": "Full",
    "baby_member": "Baby",
    "observer": "Observer",
    "alumni": "Alumni",
    "inactive": "Inactive",
}


def _optional(value: str | None) -> str:
    if not value:
        return r"\-"
    return escape_mdv2(truncate(value.strip(), FIELD_TRUNCATE_LEN))


async def get_profile_data(
    dialog_manager: DialogManager,
    l10n: FluentLocalization,
    **kwargs,
) -> dict[str, Any]:
    user = dialog_manager.event.from_user

    async with async_session() as session:
        person = await get_or_create_person(session, user.id, user.full_name, user.username)
        member = await person.awaitable_attrs.lbg_member
        await session.commit()

    if member is None:
        return {
            "is_member": False,
            "is_lbg_active": False,
            "text": l10n.format_value("profile-not-member", args={"name": escape_mdv2(person.full_name)}),
        }

    category = _CATEGORY_NAMES.get(member.membership_category, member.membership_category or r"\-")
    text = l10n.format_value(
        "profile-card",
        args={
            "name": escape_mdv2(member.full_name_ru or person.full_name),
            "category": escape_mdv2(category),
            "roles": _optional(member.status_field),
            "local_involvement": _optional(member.local_involvement),
            "international_involvement": _optional(member.international_involvement),
            "best_events": _optional(member.best_events),
        },
    )

    return {
        "is_member": True,
        "is_lbg_active": member.is_active,
        "text": text,
    }


# ========== Диалог ==========
profile_dialog = Dialog(
    Window(
        Format("{text}"),
        Start(
            L10nFormat("profile-vpn-btn"),
            id="open_vpn",
            state=ViewVpnSubscription.VIEW,
            when=F["is_lbg_active"],
        ),
        Cancel(L10nFormat("close")),
        getter=get_profile_data,
        state=ViewProfile.VIEW,
    ),
    # Профиль - точка входа: не копится в стеке при повторном /profile.
    launch_mode=LaunchMode.ROOT,
)
