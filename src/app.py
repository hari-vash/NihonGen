from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from tools import create_kanji_flashcard, check_kanji_exists
from system_prompt import system_prompt
from kanji_class import KanjiFormat
import time
import sys

model = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite"
)

agent = create_agent(
    model=model,
    system_prompt=system_prompt,
    response_format=KanjiFormat,
    tools=[check_kanji_exists, create_kanji_flashcard],
)

response = agent.invoke(
    {"messages": [HumanMessage(content="少")]}
)

parsed_response = response["structured_response"]
polished_text = parsed_response.to_polished_string()

for char in polished_text:
    sys.stdout.write(char)
    sys.stdout.flush()
    time.sleep(0.015)