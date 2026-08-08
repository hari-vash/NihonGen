from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from kanji_class import KanjiFormat
from system_prompt import system_prompt

model = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

agent = create_agent(
    model=model,
    system_prompt=system_prompt,
    format=KanjiFormat,
)

response = agent.invoke(
    {"messages": HumanMessage(content="新")}
)

print(response['messages'][-1].content[0]["text"])