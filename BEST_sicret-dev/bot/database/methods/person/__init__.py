from .create import create_person
from .read import get_person_by_id, get_person_by_telegram_id
from .update import update_person
from .delete import delete_person

__all__ = [
    'create_person',
    'get_person_by_id',
    'get_person_by_telegram_id',
    'update_person',
    'delete_person',
]

