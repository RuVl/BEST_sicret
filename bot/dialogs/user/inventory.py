from aiogram_dialog import Dialog, Window
from state_machines.inventory import ViewInventory
from middlewares import L10N_FORMAT_KEY
from utils import L10nFormat, escape_mdv2


inventory_dialog = Dialog(
    Window(
        L10nFormat('schema-not-found'),
        state=ViewInventory.CATEGORIES,
    ),
)
