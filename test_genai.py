import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json

load_dotenv()
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

async def main():
    def get_info(query: str) -> str:
        return "Info found!"
        
    chat = client.aio.chats.create(
        model="gemini-3.5-flash-lite",
        config=types.GenerateContentConfig(tools=[get_info])
    )
    
    # Try automatic?
    # Or manual?
    print("Sending message...")
    response = await chat.send_message("What is the info for 123?")
    print("Function calls:", response.function_calls)
    if response.function_calls:
        call = response.function_calls[0]
        print("Name:", call.name, "Args:", call.args)
        
        # Call it
        result = get_info(**call.args)
        
        # Send response back
        # In google-genai:
        response = await chat.send_message(
            types.Part.from_function_response(
                name=call.name,
                response={"result": result}
            )
        )
        print("Final response:", response.text)

asyncio.run(main())
