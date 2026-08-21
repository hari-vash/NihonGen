from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools

from tools import create_kanji_flashcard, check_kanji_exists
from system_prompt import system_prompt
from generation_schema import KanjiFormat
import time
import sys
import asyncio
import os

model = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite"
)

async def run_agent():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_script_path = os.path.join(current_dir, "mcp_server.py")
    
    server_params = StdioServerParameters(
        command=sys.executable, 
        args=[server_script_path], 
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            mcp_tools = await load_mcp_tools(session)
            
            all_tools = [check_kanji_exists, create_kanji_flashcard] + mcp_tools

            agent = create_agent(
                model=model,
                system_prompt=system_prompt,
                response_format=KanjiFormat,
                tools=all_tools,
            )

            print("Agent is reading the file and checking Anki...\n")
            
            file_path = input("Enter the path to your Japanese text/PDF file: ").strip()

            response = await agent.ainvoke(
                {"messages": [HumanMessage(content=f"Please read '{file_path}', extract the first chunk of kanji, and create flashcards for any I don't already know.")]}
            )
            
            parsed_response = response["structured_response"]
            polished_text = parsed_response.to_polished_string()
            
            for char in polished_text:
                sys.stdout.write(char)
                sys.stdout.flush()
                time.sleep(0.015)

if __name__ == "__main__":
    asyncio.run(run_agent())