from dotenv import load_dotenv
load_dotenv()

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI

from kanji_class import KanjiFormat
from tools import check_kanji_exists,create_kanji_flashcards

model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite"
)

structured_model = model.with_structured_output(KanjiFormat)

class State(TypedDict):
    kanji: str
    deck: str
    meaning: KanjiFormat
    lesson:str
    exists: bool
    anki_status: str

def analyze_kanji(state:State):
    response = structured_model.invoke(f"Generate the meaning of this japanese kanji: {state["kanji"]}")
    return {"meaning":response}

def generate_lesson(state: State):
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

def check_anki(state: State):
    exists = check_kanji_exists.invoke({
        "kanji": state["kanji"],
        "deck": state["deck"],
    })

    return {
        "exists": exists
    }

def route_anki(state: State):
    if state["exists"]:
        return "already_exists"

    return "create_flashcard"

def create_flashcard(state: State):
    meaning = state["meaning"]

    result = create_kanji_flashcards.invoke({
        "kanji": state["kanji"],
        "deck": state["deck"],
        "onyomi": meaning.onyomi,
        "kunyomi": meaning.kunyomi,
        "kanji_meaning": meaning.kanji_meaning,
        "onyomi_examples": meaning.onyomi_examples,
        "kunyomi_examples": meaning.kunyomi_examples,
    })

    return {
        "anki_status": result
    }

builder = StateGraph(State)

builder.add_node("analyze_kanji", analyze_kanji)
builder.add_node("generate_lesson", generate_lesson)
builder.add_node("check_anki", check_anki)
builder.add_node("create_flashcard", create_flashcard)

builder.add_edge(START, "analyze_kanji")
builder.add_edge("analyze_kanji","generate_lesson")
builder.add_edge("generate_lesson", "check_anki")

builder.add_conditional_edges(
    "check_anki",
    route_anki,
    {
        "already_exists": END,
        "create_flashcard": "create_flashcard",
    }
)

builder.add_edge("create_flashcard", END)

graph = builder.compile()

result = graph.invoke({
    "kanji": "間",
    "deck": "Test_Deck1",
})

polished_text = result["meaning"].to_polished_string()
print(polished_text)
print("="*20)
print("\nConverstaion Lesson\n")
print("="*20)
print(result["lesson"])
print("\n")
print(result.get("anki_status", "Already exists in Anki."))