"""Тестовый скрипт для проверки подключения к обоим портам PostgreSQL"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from env import PostgresKeys

async def test_port(port, description):
    print(f"\n=== Testing {description} (port {port}) ===")
    # Используем те же настройки, но с другим портом
    test_url = PostgresKeys.URL.replace(f":{PostgresKeys.PORT}", f":{port}")
    print(f"URL: {test_url.replace(PostgresKeys.PASSWORD, '***')}")
    
    engine = create_async_engine(test_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute("SELECT version();")
            version = result.scalar()
            print(f"[SUCCESS] Connected! PostgreSQL version: {version[:50]}...")
            await conn.close()
            await engine.dispose()
            return True
    except Exception as e:
        print(f"[ERROR] Connection failed: {type(e).__name__}: {e}")
        await engine.dispose()
        return False

async def main():
    print("Current configuration:")
    print(f"  Host: {PostgresKeys.HOST}")
    print(f"  Port: {PostgresKeys.PORT}")
    print(f"  User: {PostgresKeys.USER}")
    print(f"  Database: {PostgresKeys.DATABASE}")
    
    # Тестируем оба порта
    port_5432 = await test_port(5432, "Local PostgreSQL")
    port_5433 = await test_port(5433, "Docker PostgreSQL")
    
    print("\n=== Summary ===")
    if port_5432:
        print("Port 5432 (local): OK")
    else:
        print("Port 5432 (local): FAILED")
    
    if port_5433:
        print("Port 5433 (Docker): OK")
    else:
        print("Port 5433 (Docker): FAILED")

if __name__ == "__main__":
    asyncio.run(main())

