import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def kill():
    engine = create_async_engine('postgresql+asyncpg://postgres:admin@localhost:5432/postgres')
    async with engine.connect() as conn:
        await conn.execute(text('''
            SELECT pg_terminate_backend(pid) 
            FROM pg_stat_activity 
            WHERE datname = 'careflow_test';
        '''))
        await conn.commit()
    await engine.dispose()
    print('Killed')

if __name__ == '__main__':
    asyncio.run(kill())
