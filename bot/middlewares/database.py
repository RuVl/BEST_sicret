from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.main import async_session
from middlewares import SESSION_KEY


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware для управления соединениями с базой данных.

    Создает сессию БД только для хэндлеров, помеченных флагом 'requires_db'.
    Если middleware применен к роутеру напрямую (например, для диалогов),
    все хэндлеры в этом роутере автоматически получат сессию.
    
    ⚠️ ВАЖНО: Middleware НЕ выполняет автоматический commit!
    
    СТРАТЕГИЯ: Explicit transaction management
    ────────────────────────────────────────
    Handlers отвечают за явное управление транзакциями:
    - Middleware предоставляет сессию в data[SESSION_KEY]
    - Database методы используют только await session.flush()
    - Handler ЯВНО вызывает await session.commit() для сохранения
    - При ошибке session.rollback() вызовется автоматически
    
    ✅ ПРИМЕР ПРАВИЛЬНОГО ИСПОЛЬЗОВАНИЯ:
    
    @router.message(CommandStart())
    async def start(msg: Message, session: AsyncSession):
        person = await get_person_by_telegram_id(session, msg.from_user.id)
        if person is None:
            person = await create_person(session, msg.from_user.id, name)
            await session.flush()  # Database method flushes
            # 👇 Handler явно коммитит
            await session.commit()
        return person
    
    ПОЧЕМУ ТАК?
    ──────────
    - Atomic: Несколько DB операций коммитятся вместе
    - Explicit: Порядок commit визуально понятен из кода handler
    - Controllable: Handler решает когда коммитить (с условиями, перепроверками и т.д.)
    """

    def __init__(self, always_create_session: bool = False):
        """
        Args:
            always_create_session: Если True, всегда создает сессию без проверки флагов.
                                   Используется при применении middleware к роутеру напрямую.
        """
        self.always_create_session = always_create_session

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        """
        Открывает сессию БД только если:
        - always_create_session=True (применен к роутеру напрямую), ИЛИ
        - хэндлер помечен флагом requires_db=True

        Сессия автоматически закрывается после выполнения хэндлера.
        """
        # Если middleware применен к роутеру напрямую, всегда создаем сессию
        if self.always_create_session:
            return await self._create_session_and_call(handler, event, data)

        # Проверяем, не является ли это диалогом (диалоги имеют DialogManager в data)
        # Если это диалог, пропускаем (для диалогов есть отдельный middleware)
        if "dialog_manager" in data:
            return await handler(event, data)

        # Проверяем флаг хэндлера
        # В aiogram 3.x флаги могут быть в data["flags"] или в handler.flags
        flags = data.get("flags", {})
        # Также проверяем handler.flags, если он есть
        handler_obj = data.get("handler")
        if handler_obj:
            # Проверяем разные способы получения флагов
            if hasattr(handler_obj, "flags"):
                flags = {**flags, **handler_obj.flags}
            elif hasattr(handler_obj, "callback") and hasattr(handler_obj.callback, "__flags__"):
                # Флаги могут быть в __flags__ атрибуте callback
                callback_flags = getattr(handler_obj.callback, "__flags__", {})
                flags = {**flags, **callback_flags}

        requires_db = flags.get("requires_db", False)

        # Если флаг не установлен, пропускаем middleware
        if not requires_db:
            return await handler(event, data)

        # Создаем сессию для хэндлеров с флагом
        return await self._create_session_and_call(handler, event, data)

    async def _create_session_and_call(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        """
        Вспомогательный метод для создания сессии и вызова хэндлера.
        
        ВНИМАНИЕ: Middleware НЕ выполняет автоматический commit!
        Это следует выбранной стратегии ЯВНОГО управления транзакциями.
        
        ОТВЕТСТВЕННОСТЬ HANDLER ЗАКРЫТА:
        1. Создать сессию (достается из data[SESSION_KEY])
        2. Вызвать database методы (используют только flush)
        3. ЯВНО вызвать await session.commit() если операция успешна
        4. При ошибкe session.rollback() вызывается контекстом or явно в except блоке
        
        СТРАТЕГИЯ: Explicit transaction management
        - Middleware предоставляет сессию
        - Handler отвечает за commit/rollback
        - Database методы используют только flush
        - Атомарность достигается через контролируемые commits в handler коде
        """
        async with async_session() as session:
            data[SESSION_KEY] = session
            try:
                result = await handler(event, data)
                # ✅ ЯВНОЕ управление: НЕ делаем автоматический commit
                # Handler отвечает за явный await session.commit()
                return result
            except Exception:
                # При исключении откатываем изменения, которые были flush'ены
                await session.rollback()
                raise
