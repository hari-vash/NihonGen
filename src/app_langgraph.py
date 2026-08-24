from dotenv import load_dotenv
load_dotenv()

import os
import sys
import asyncio
import json

from typing import NotRequired

from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt,Command
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from generation_schema import KanjiFormat, KanjiLesson, QuizEvaluation
from tools import check_kanji_exists, create_kanji_flashcards
from system_prompts import kanji_generation_prompt,lesson_generation_prompt,quiz_question_prompt

model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite"
)

structured_model_kanji = model.with_structured_output(KanjiFormat)
structured_model_lesson = model.with_structured_output(KanjiLesson)
structured_quiz_model = model.with_structured_output(QuizEvaluation)

memory = MemorySaver()

MAX_QUIZ_ROUNDS = 6

class State(MessagesState):
    # Document
    file_path: str
    session_id: str
    current_chunk: list[str]
    current_index: int
    has_more: bool

    # Anki
    deck: str
    exists: bool
    anki_status: NotRequired[str]

    # Current kanji
    kanji: str
    meaning: KanjiFormat
    lesson: KanjiLesson

    # Quiz
    quiz_round: int
    quiz_evaluation: NotRequired[QuizEvaluation]
    quiz_passed: NotRequired[bool]

    # HITL
    user_decision: NotRequired[str]

# helper function for mcp
def parse_mcp_json(result):
    if not result.content:
        raise RuntimeError("MCP server returned no content.")

    text = result.content[0].text

    return json.loads(text)

def normalize_yes_no(text: str) -> str:
    text = text.lower().strip()

    positive = {"yes","y","yeah","yep","sure","go ahead","yes absolutely","absolutely","okay","ok","ready","let's go"}

    negative = {"no","n","not yet","i don't understand","i still don't understand","i have doubts","explain more","explain again",}

    if text in positive:
        return "ready"

    if text in negative:
        return "needs_explanation"

    # for ambigious input
    return "needs_explanation"

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

        return {"lesson": response}

    def quiz_readiness(state: State):
        decision = interrupt({"type": "quiz_readiness",
            "message": f"Are you ready for a quiz testing your knowledge about the kanji {state['kanji']}?"})

        return {"user_decision": decision}

    def route_quiz_readiness(state: State):
        return normalize_yes_no(state["user_decision"])

    def explain_again(state: State):
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a patient Japanese teacher. "
                        "Re-explain the kanji using the already generated "
                        "information below. Do not introduce contradictory "
                        "information. Make the explanation simpler and clearer."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Kanji: {state['kanji']}\n\n"
                        f"Kanji information:\n"
                        f"{state['meaning'].model_dump_json()}\n\n"
                        f"Lesson:\n"
                        f"{state['lesson'].to_polished_string()}"
                    )
                ),
            ]
        )

        print("\nAdditional explanation:")
        print(response.content)

        return {
            "quiz_round": 0
        }
        
    def generate_quiz_question(state: State):
        prompt = quiz_question_prompt(
            kanji=state["kanji"],
            lesson=state["lesson"].to_polished_string(),
            round_number=state["quiz_round"] + 1,
        )

        response = model.invoke([prompt])

        return {
            "messages": [response]
        }
    
    def wait_for_answer(state: State):
    question = state["messages"][-1].content

    print("\nQuiz:")
    print(question)

    answer = interrupt({
        "type": "quiz_answer",
        "question": question,
        "kanji": state["kanji"],
    })

    return {
        "messages": [
            HumanMessage(content=answer)
        ]
    }
    
    def evaluate_quiz_answer(state: State):
        prompt = SystemMessage(
            content=f"""
            You are evaluating a Japanese learner's answer.

            Target kanji:
            {state['kanji']}

            Lesson:
            {state['lesson'].to_polished_string()}

            The student should be evaluated on understanding,
            correctness, kanji usage, and relevant Japanese grammar.

            Decide whether the student has demonstrated enough understanding
            to move on.

            Do NOT be overly harsh, but do not mark incorrect answers as correct.
            """
        )

        response = structured_quiz_model.invoke([
            prompt,
            *state["messages"]
        ])

        return {
            "quiz_evaluation": response,
            "quiz_passed": response.mastered,
            "quiz_round": state["quiz_round"] + 1,
            "messages": [
                AIMessage(
                    content=(
                        f"{response.feedback}\n\n"
                        f"{response.explanation}"
                    )
                )
            ],
        }
    
    def route_quiz(state: State):
        evaluation = state["quiz_evaluation"]

        if evaluation.mastered:
            return "quiz_passed"

        if state["quiz_round"] >= MAX_QUIZ_ROUNDS:
            return "quiz_passed"

        return "next_question"
    
    def check_anki(state: State):
        exists = check_kanji_exists.invoke({
            "kanji": state["kanji"],
            "deck": state["deck"],
        })

        return {"exists": exists}


    def route_anki(state: State):
        if state["exists"]:
            return "update_approval"

        return "create_approval"

    def approve_update(state: State):
        decision = interrupt({
            "type": "anki_update_approval",
            "message": (
                f"The kanji {state['kanji']} already exists in "
                f"the Anki deck '{state['deck']}'.\n\n"
                "Do you want to update the existing flashcard "
                "with the newly generated content?"
            )
        })

        return {
            "user_decision": decision
        }

    def route_update_approval(state: State):
        return normalize_yes_no(state["user_decision"])
    
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
    
    def quiz_master(state:State):
        response = model.invoke([
            quiz_generation_prompt(kanji=state['kanji'],lesson=state['lesson'].to_polished_string()),*state['messages']
        ])
        return {"messages":[response]}
        
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
    builder.add_node("quiz_master",quiz_master)
    
    # Edges
    builder.add_edge(START,"initialize_document")
    builder.add_edge("initialize_document","select_kanji")
    builder.add_edge("select_kanji","analyze_kanji")
    builder.add_edge("analyze_kanji","generate_lesson")
    builder.add_edge("generate_lesson","print_lesson")
    builder.add_conditional_edges("quiz_readiness",
    route_quiz_readiness,
    {
        "ready": "generate_quiz_question",
        "needs_explanation": "explain_again",
    })
    builder.add_edge("explain_again","generate_quiz_question")
    builder.add_edge("generate_quiz_question","wait_for_answer")
    builder.add_edge("wait_for_answer","evaluate_quiz_answer")
    builder.add_conditional_edges("evaluate_quiz_answer",
    route_quiz,
    {
        "next_question": "generate_quiz_question",
        "quiz_passed": "check_anki",
    })
    builder.add_edge("print_lesson","check_anki")
    builder.add_conditional_edges(
        "approve_update",
        route_update_approval,
        {
            "ready": "update_flashcard",
            "needs_explanation": "advance_kanji",
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

    graph = builder.compile(checkpointer=memory)
    config = {"configurable":{"thread_id":"kanji_convo_1"}}
    
    return graph,config

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

            graph,config = build_graph(session)

            file_path = input(
                "Enter the path to your Japanese text/PDF file: "
            ).strip()

            result = await graph.ainvoke({
                "file_path": file_path,
                "deck": "Test_Deck1",
            },config=config)

            print("\nProcessing complete.")

if __name__ == "__main__":
    asyncio.run(run_app())