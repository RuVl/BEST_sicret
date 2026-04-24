from aiogram import F
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Row, ScrollingGroup, Select
from aiogram_dialog.widgets.text import Format, Multi

from state_machines import CreateByRefund
from utils import L10nFormat

refund_dialog = Dialog(
    # Window(
    #     Multi(Format("{view}\n"), sep=""),
    #     ScrollingGroup(
    #         Select(
    #             Format("{item[0]}"),
    #             id="refund_field",
    #             item_id_getter=lambda x: x[1],
    #             items="data_kb",
    #             on_click=on_refund_data_selected,
    #         ),
    #         id="refund_scroll",
    #         width=2,
    #         height=5,
    #         hide_on_single_page=True,
    #     ),
    #     Row(
    #         Button(
    #             L10nFormat("refund_send_button"),
    #             id="refund_send",
    #             on_click=on_refund_send,
    #             when=F["can_send"],
    #         )
    #     ),
    #     getter=get_refund_view,
    #     state=CreateByRefund.VIEW,
    # ),
    # Window(
    #     Format("{question}"),
    #     MessageInput(set_refund_property),
    #     Row(
    #         Button(
    #             L10nFormat("refund_back_button"),
    #             id="refund_back",
    #             on_click=lambda c, w, m: m.switch_to(CreateByRefund.VIEW),
    #         )
    #     ),
    #     getter=get_refund_edit,
    #     state=CreateByRefund.EDIT,
    # ),
)
