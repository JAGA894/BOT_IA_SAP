import asyncio
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

async def test():
    client = genai.Client()
    try:
        r = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents='Hola'
        )
        print("2.5-flash OK:", r.text)
    except Exception as e:
        print("2.5-flash Error:", e)

asyncio.run(test())
