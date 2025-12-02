"""Проверка существующих баз данных и создание нужной"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from env import PostgresKeys

async def check_databases():
    # Подключаемся к системной базе данных postgres
    postgres_url = PostgresKeys.URL.replace(f"/{PostgresKeys.DATABASE}", "/postgres")
    
    print("=== Checking Databases ===")
    print(f"Host: {PostgresKeys.HOST}")
    print(f"Port: {PostgresKeys.PORT}")
    print(f"User: {PostgresKeys.USER}")
    print(f"Requested Database: {PostgresKeys.DATABASE}")
    print()
    
    engine = create_async_engine(postgres_url)
    try:
        async with engine.connect() as conn:
            # Получаем список баз данных
            result = await conn.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false;"))
            databases = [row[0] for row in result]
            
            print(f"[SUCCESS] Connected to PostgreSQL!")
            print(f"\nAvailable databases: {', '.join(databases)}")
            
            # Проверяем, существует ли нужная база данных
            if PostgresKeys.DATABASE in databases:
                print(f"\n[OK] Database '{PostgresKeys.DATABASE}' exists!")
                return True
            else:
                print(f"\n[WARNING] Database '{PostgresKeys.DATABASE}' does NOT exist!")
                print(f"\nAvailable databases are: {', '.join(databases)}")
                
                # Предлагаем создать базу данных
                print(f"\nWould you like to create database '{PostgresKeys.DATABASE}'?")
                return False
            
            await conn.close()
    except Exception as e:
        print(f"[ERROR] Connection failed: {type(e).__name__}: {e}")
        return False
    finally:
        await engine.dispose()

async def create_database():
    """Создание базы данных"""
    postgres_url = PostgresKeys.URL.replace(f"/{PostgresKeys.DATABASE}", "/postgres")
    engine = create_async_engine(postgres_url)
    
    try:
        async with engine.connect() as conn:
            # Отключаем автокоммит для создания базы данных
            await conn.execute(text(f"CREATE DATABASE {PostgresKeys.DATABASE};"))
            await conn.commit()
            print(f"[SUCCESS] Database '{PostgresKeys.DATABASE}' created!")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to create database: {type(e).__name__}: {e}")
        return False
    finally:
        await engine.dispose()

async def main():
    exists = await check_databases()
    
    if not exists:
        print("\n=== Creating Database ===")
        await create_database()
        # Проверяем снова
        print("\n=== Verifying ===")
        await check_databases()

if __name__ == "__main__":
    asyncio.run(main())

