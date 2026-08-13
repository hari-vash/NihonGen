from dotenv import load_dotenv
load_dotenv()

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI

model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite"
)

class State(TypedDict):
    kanji: str
    meaning: str

def call_model(state:State):
    response = model.invoke(f"Generate the meaning of this japanese kanji: {state["kanji"]}")
    return {"meaning":response.content[0]["text"]}

builder = StateGraph(State)

builder.add_node("calling_model",call_model)

builder.add_edge(START,"calling_model")
builder.add_edge("calling_model",END)

graph = builder.compile()

result = graph.invoke({
    "kanji": "多"
})

print(result["meaning"])