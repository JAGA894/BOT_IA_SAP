import asyncio
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

async def test():
    client = genai.Client()
    try:
        r = await client.aio.models.generate_content(
            model='gemini-flash-latest',
            contents='Hola'
        )
        print("latest OK:", r.text)
    except Exception as e:
        print("latest Error:", e)

asyncio.run(test())
