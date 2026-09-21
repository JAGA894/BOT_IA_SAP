import asyncio
import os
from google import genai
from google.genai import types

async def test():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        r = await client.aio.models.generate_content(
            model='gemini-3.5-flash',
            contents='Hola'
        )
        print("3.5-flash OK:", r.text)
    except Exception as e:
        print("3.5-flash Error:", e)

asyncio.run(test())
