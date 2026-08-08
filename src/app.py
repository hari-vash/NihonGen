from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from kanji_class import KanjiFormat
from system_prompt import system_prompt
from tools import check_kanji_exists,create_kanji_flashcard
import time
import sys

model = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

agent = create_agent(
    model=model,
    system_prompt=system_prompt,
    response_format=KanjiFormat,
    tools=[check_kanji_exists,create_kanji_flashcard]
)

response = agent.invoke(
    {"messages": HumanMessage(content="新")}
)

parsed_response = response["structured_response"]
polished_text = parsed_response.to_polished_string()

for char in polished_text:
    sys.stdout.write(char)
    sys.stdout.flush()
    time.sleep(0.015)