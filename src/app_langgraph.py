from dotenv import load_dotenv
load_dotenv()

import os
import sys
import asyncio
import json

from typing import NotRequired
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from generation_schema import KanjiFormat, KanjiLesson
from tools import check_kanji_exists, create_kanji_flashcards
from system_prompts import kanji_generation_prompt,lesson_generation_prompt,quiz_generation_prompt

model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite"
)

structured_model_kanji = model.with_structured_output(KanjiFormat)
structured_model_lesson = model.with_structured_output(KanjiLesson)

class State(TypedDict):
    file_path: str
    deck: str

    session_id: str
    current_chunk: list[str]
    current_index: int
    has_more: bool

    kanji: str
    meaning: KanjiFormat
    lesson: KanjiLesson
    exists: bool
    anki_status: NotRequired[str]

# helper function for mcp
def parse_mcp_json(result):
    if not result.content:
        raise RuntimeError("MCP server returned no content.")

    text = result.content[0].text

    return json.loads(text)

def build_graph(session):
    
    async def initialize_document(state: State):

        result = await session.call_tool(
            "initialize_file_stream",
            {
                "file_path": state["file_path"]
            }
        )

        data = parse_mcp_json(result)

        if data.get("status") != "success":
            raise RuntimeError(
                data.get(
                    "error",
                    data.get(
                        "message",
                        "MCP initialization failed."
                    )
                )
            )

        return {
            "session_id": data["session_id"],
            "current_chunk": data["current_chunk"],
            "current_index": 0,
            "has_more": data["has_more"],
        }


    async def get_next_chunk(state: State):

        result = await session.call_tool(
            "get_next_kanji_chunk",
            {
                "session_id": state["session_id"]
            }
        )

        data = parse_mcp_json(result)

        return {
            "current_chunk": data.get("current_chunk", []),
            "current_index": 0,
            "has_more": data.get("has_more", False),
        }

    def select_kanji(state: State):
        return {"kanji": state["current_chunk"][state["current_index"]]}


    def analyze_kanji(state: State):
        kanji_prompt = kanji_generation_prompt(state['kanji'])
        response = structured_model_kanji.invoke(kanji_prompt)

        return {"meaning": response}


    def generate_lesson(state: State):
        lesson_prompt = lesson_generation_prompt(
            kanji=state['kanji'],
            onyomi=state['meaning'].onyomi,
            kunyomi=state['meaning'].kunyomi,
            kanji_meaning=state['meaning'].kanji_meaning)
        response = structured_model_lesson.invoke(lesson_prompt)

        return {"lesson": response.content[0]["text"]}

    def check_anki(state: State):
        exists = check_kanji_exists.invoke({
            "kanji": state["kanji"],
            "deck": state["deck"],
        })

        return {"exists": exists}


    def route_anki(state: State):
        if state["exists"]:
            return "already_exists"
        return "create_flashcard"


    def create_flashcard(state: State):

        meaning = state["meaning"]

        result = create_kanji_flashcards.invoke({
            "kanji": state["kanji"],
            "onyomi": meaning.onyomi,
            "kunyomi": meaning.kunyomi,
            "kanji_meaning": meaning.kanji_meaning,
            "deck": state["deck"],
            "onyomi_examples": meaning.onyomi_examples,
            "kunyomi_examples": meaning.kunyomi_examples,
        })

        return {"anki_status": result}

    def print_lesson(state: State):
        print("\n" + "=" * 50)
        print(f"KANJI: {state['kanji']}")
        print("=" * 50)
        print(state["meaning"].to_polished_string())
        print("\nLesson:")
        print(state["lesson"])
        print()

    def advance_kanji(state: State):
        return {"current_index": state["current_index"] + 1}


    def route_chunk(state: State):
        if state["current_index"] < len(state["current_chunk"]):
            return "select_kanji"
        return "get_next_chunk"


    def route_document(state: State):
        if state["has_more"]:
            return "select_kanji"
        return "finish"

    builder = StateGraph(State)

    # Nodes
    builder.add_node("initialize_document",initialize_document)
    builder.add_node("select_kanji",select_kanji)
    builder.add_node("analyze_kanji",analyze_kanji)
    builder.add_node("generate_lesson",generate_lesson)
    builder.add_node("print_lesson",print_lesson)
    builder.add_node("check_anki",check_anki)
    builder.add_node("create_flashcard",create_flashcard)
    builder.add_node("advance_kanji",advance_kanji)
    builder.add_node("get_next_chunk",get_next_chunk)

    # Edges
    builder.add_edge(START,"initialize_document")
    builder.add_edge("initialize_document","select_kanji")
    builder.add_edge("select_kanji","analyze_kanji")
    builder.add_edge("analyze_kanji","generate_lesson")
    builder.add_edge("generate_lesson","print_lesson")
    builder.add_edge("print_lesson","check_anki")
    builder.add_conditional_edges("check_anki",
        route_anki,
        {
            "already_exists": "advance_kanji",
            "create_flashcard": "create_flashcard",
        })
    builder.add_edge("create_flashcard","advance_kanji")
    builder.add_conditional_edges("advance_kanji",
        route_chunk,
        {
            "select_kanji": "select_kanji",
            "get_next_chunk": "get_next_chunk",
        })
    builder.add_conditional_edges("get_next_chunk",
        route_document,
        {
            "select_kanji": "select_kanji",
            "finish": END,
        })

    graph = builder.compile()
    return graph

async def run_app():

    current_dir = os.path.dirname(os.path.abspath(__file__))

    server_script_path = os.path.join(current_dir,"mcp_server.py")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script_path],
    )

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            graph = build_graph(session)

            file_path = input(
                "Enter the path to your Japanese text/PDF file: "
            ).strip()

            result = await graph.ainvoke({
                "file_path": file_path,
                "deck": "Test_Deck1",
            })

            print("\nProcessing complete.")

if __name__ == "__main__":
    asyncio.run(run_app())