import asyncio
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

async def test():
    client = genai.Client()
    for m in client.models.list():
        if 'flash' in m.name:
            print(m.name)

asyncio.run(test())
