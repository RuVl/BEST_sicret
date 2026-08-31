from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from env import PostgresKeys

engine = create_async_engine(PostgresKeys.URL)
async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def create_schema() -> None:
    """Создать таблицу(ы) сервиса, если их ещё нет (идемпотентно, для dev).

    В проде схему создаёт единый alembic из ``packages/db``. Здесь импортируется
    только ``LbgMember``, поэтому ``create_all`` затронет лишь ``lbg_members``.
    См. ``SyncKeys.AUTO_CREATE_SCHEMA``.
    """
    from best_db.models import Base, LbgMember

    async with engine.begin() as conn:
        # Только своя таблица: общий Base.metadata содержит и таблицы бота.
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[LbgMember.__table__]))
