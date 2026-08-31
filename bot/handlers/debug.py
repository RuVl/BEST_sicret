from aiogram import F, Router
from aiogram.types import Message

router = Router()


@router.message(F.entities.extract(F.type == "custom_emoji"))
async def get_custom_emoji_id(msg: Message) -> None:
    emoji_entities = filter(lambda entity: entity.type == "custom_emoji", msg.entities)
    custom_emoji_ids = (f"`{entity.custom_emoji_id}`" for entity in emoji_entities)

    text = "Все id кастомных смайликов в тексте:\n" + "\n".join(custom_emoji_ids)
    await msg.answer(text)
