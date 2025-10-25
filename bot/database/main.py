from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from env import PostgresKeys

engine = create_async_engine(PostgresKeys.URL)
async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
	bind=engine,
	expire_on_commit=False
)