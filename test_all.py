import asyncio
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

models = [
    'gemini-3.1-flash-lite',
    'gemini-3.5-flash-lite',
    'gemini-3.6-flash',
    'gemini-3.7-flash',
    'gemini-3.8-flash'
]

async def test():
    client = genai.Client()
    for m in models:
        try:
            r = await client.aio.models.generate_content(model=m, contents='Hola')
            print(f"{m} OK: {r.text.strip()}")
        except Exception as e:
            print(f"{m} Error: {e}")

asyncio.run(test())
