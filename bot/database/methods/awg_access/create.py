from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AwgAccess


async def create_access(session: AsyncSession, *, person_id: int, client_name: str) -> AwgAccess:
    """Выдать разрешение. Ключ в панели появится при первом запросе конфига. Коммит - на вызывающей стороне."""
    access = AwgAccess(person_id=person_id, client_name=client_name, status="granted")
    session.add(access)
    await session.flush()
    return access
