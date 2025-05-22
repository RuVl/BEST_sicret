from typing import Any, Protocol

from aiogram_dialog.api.protocols import DialogManager
from aiogram_dialog.widgets.common import WhenCondition
from aiogram_dialog.widgets.text import Text

from middlewares import L10N_FORMAT_KEY


class Values(Protocol):
	def __getitem__(self, item: Any) -> Any:
		raise NotImplementedError


class L10nFormat(Text):
	def __init__(self, key: str, args: dict[str, Any] | None = None, when: WhenCondition = None):
		super().__init__(when)
		self.key = key
		self.args = args or {}

	async def _render_text(self, data: dict, manager: DialogManager) -> str:
		l10n = manager.middleware_data.get(L10N_FORMAT_KEY)
		return l10n.format_value(self.key, args=self.args | data)
