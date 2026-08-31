"""Главное меню ``/start``: карточка мембера и вход во внутренние диалоги.

Данные о человеке - readonly-слепок из гугл-таблицы (``LbgMember``, синхронизируется
members_sync). Не опознанным пользователям показываем приветствие с приглашением вступить.

Меню - единственная точка входа: команд для приказов, заявок и имущества больше нет,
поэтому кнопки видны только состоящим в группе (``current_member``).
"""

from typing import Any

from aiogram import F
from aiogram_dialog import Dialog, DialogManager, LaunchMode, Window
from aiogram_dialog.widgets.kbd import Start
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization

from database.main import async_session
from database.methods.person import get_or_create_person, get_person_with_member
from state_machines.apply_eq import CreateByApplyEquipment
from state_machines.inventory import ViewInventory
from state_machines.profile import ViewProfile
from state_machines.refund import CreateRefundApply
from state_machines.templates import CreateByTemplate
from state_machines.vpn import ViewVpnSubscription
from utils import L10nFormat, current_member, escape_mdv2, truncate

FIELD_TRUNCATE_LEN = 200

# Человекочитаемые названия категорий членства (значения проставляет members_sync).
_CATEGORY_NAMES = {
    "board": "BOARD",
    "full_member": "Full",
    "baby_member": "Baby",
    "observer": "Observer",
    "guest": "Guest",
    "abroad": "Abroad",
    "alumni": "Alumni",
    "former": "Former",
    "inactive": "Inactive",
    "ex_member": "Ex-member",
    "ex_full_member": "Ex-full",
    "ex_baby_member": "Ex-baby",
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
        await session.commit()
        # Перечитываем с joinedload: предикат доступа трогает lbg_member уже вне сессии.
        person = await get_person_with_member(session, user.id)

    member = person.lbg_member if person else None

    if member is None:
        return {
            "is_member": False,
            "text": l10n.format_value("profile-not-member", args={"name": escape_mdv2(user.full_name)}),
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

    # Кнопки меню - только состоящим в группе; ex-мембер видит карточку без них.
    return {
        "is_member": current_member(person) is not None,
        "text": text,
    }


# ========== Диалог ==========
profile_dialog = Dialog(
    Window(
        Format("{text}"),
        Start(
            L10nFormat("menu-document-btn"),
            id="open_document",
            state=CreateByTemplate.CHOOSE_TEMPLATE,
            when=F["is_member"],
        ),
        Start(
            L10nFormat("menu-equipment-apply-btn"),
            id="open_equipment_apply",
            state=CreateByApplyEquipment.VIEW,
            when=F["is_member"],
        ),
        Start(
            L10nFormat("menu-refund-btn"),
            id="open_refund",
            state=CreateRefundApply.VIEW,
            when=F["is_member"],
        ),
        Start(
            L10nFormat("menu-inventory-btn"),
            id="open_inventory",
            state=ViewInventory.SELECT_CATEGORY,
            when=F["is_member"],
        ),
        Start(
            L10nFormat("profile-vpn-btn"),
            id="open_vpn",
            state=ViewVpnSubscription.VIEW,
            when=F["is_member"],
        ),
        getter=get_profile_data,
        state=ViewProfile.VIEW,
    ),
    # Профиль - точка входа: не копится в стеке при повторном /profile.
    launch_mode=LaunchMode.ROOT,
)
