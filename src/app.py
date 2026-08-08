from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.messages import HumanMessage

model = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

agent = create_agent(
    model=model,
)

response = agent.invoke(
    {"messages": HumanMessage(content="Hello")}
)

print(response['messages'][-1].content[0]["text"])