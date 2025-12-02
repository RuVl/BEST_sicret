"""Тестовый скрипт для проверки подключения к базе данных"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from env import PostgresKeys

async def test_connection():
    print("=== Testing Database Connection ===")
    print(f"Host: {PostgresKeys.HOST}")
    print(f"Port: {PostgresKeys.PORT}")
    print(f"User: {PostgresKeys.USER}")
    print(f"Database: {PostgresKeys.DATABASE}")
    print(f"URL: {PostgresKeys.URL.replace(PostgresKeys.PASSWORD, '***')}")
    print()
    
    engine = create_async_engine(PostgresKeys.URL)
    try:
        print("Attempting to connect...")
        async with engine.connect() as conn:
            print("[SUCCESS] Connection successful!")
            # Выполняем простой запрос
            result = await conn.execute("SELECT version();")
            version = result.scalar()
            print(f"PostgreSQL version: {version[:50]}...")
            await conn.close()
        print("[SUCCESS] Connection test passed!")
        return True
    except Exception as e:
        print(f"[ERROR] Connection failed: {type(e).__name__}: {e}")
        return False
    finally:
        await engine.dispose()

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    exit(0 if success else 1)

