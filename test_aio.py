import asyncio
import aiosqlite

async def test():
    async with aiosqlite.connect('bot_ia.db', timeout=15.0) as db:
        print("Connected!")

asyncio.run(test())
