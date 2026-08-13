from dotenv import load_dotenv
load_dotenv()

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from kanji_class import KanjiFormat

model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite"
)

structured_model = model.with_structured_output(KanjiFormat)

class State(TypedDict):
    kanji: str
    meaning: KanjiFormat
    lesson: str

def analyze_kanji(state:State):
    response = structured_model.invoke(f"Generate the meaning of this japanese kanji: {state["kanji"]}")
    return {"meaning":response}

def create_lesson(state: State):
    response = model.invoke(
        f"""
        Teach a Japanese beginner about the kanji:

        Kanji: {state['kanji']}
        Meaning: {state['meaning'].kanji_meaning}
        On'yomi: {state['meaning'].onyomi}
        Kun'yomi: {state['meaning'].kunyomi}

        Explain when these readings are used along with a small example conversation.
        """
    )

    return {
        "lesson": response.content[0]["text"]
    }
    
builder = StateGraph(State)

builder.add_node("analyze_kanji", analyze_kanji)
builder.add_node("create_lesson", create_lesson)

builder.add_edge(START, "analyze_kanji")
builder.add_edge("analyze_kanji", "create_lesson")
builder.add_edge("create_lesson", END)

graph = builder.compile()

result = graph.invoke({
    "kanji": "多"
})

polished_text = result["meaning"].to_polished_string()
print(polished_text)
print("="*20)
print("\nConverstaion Lesson\n")
print("="*20)
print(result["lesson"])