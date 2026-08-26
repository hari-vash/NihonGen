from dotenv import load_dotenv

load_dotenv()

import asyncio
import json
import os
import sys
import uuid
from typing import NotRequired

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command, interrupt

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from generation_schema import KanjiFormat, KanjiLesson, QuizEvaluation
from system_prompts import kanji_generation_prompt,lesson_generation_prompt,quiz_question_prompt
from tools import check_kanji_exists,create_kanji_flashcards,update_kanji_flashcard

model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite"
)

structured_kanji_model = model.with_structured_output(KanjiFormat)
structured_lesson_model = model.with_structured_output(KanjiLesson)
structured_quiz_model = model.with_structured_output(QuizEvaluation)

memory = MemorySaver()

MAX_QUIZ_ROUNDS = 6

class State(MessagesState):
    # Document / MCP
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


# helping functions
def parse_mcp_json(result):
    """Parse the JSON string returned by an MCP tool."""
    if not result.content:
        raise RuntimeError("MCP server returned no content.")

    text = result.content[0].text
    return json.loads(text)


def normalize_yes_no(text: str) -> str:
    """
    Convert common natural-language confirmations/rejections into deterministic routing labels.
    Returns:
        approve
        reject
        clarify
    """
    text = text.lower().strip()

    positive_phrases = ("yes","yeah","yep","yup","sure","absolutely","definitely","go ahead","let's go","lets go","ready","okay","ok","sounds good","do it","please do","i'm ready","im ready")

    negative_phrases = ("no","nope","not yet","i don't understand","i dont understand","i still don't understand","i still dont understand","i have doubts","i have a doubt","explain more","explain again","please explain","i'm confused","im confused","i don't get it","i dont get it")

    if any(phrase in text for phrase in positive_phrases):
        return "approve"

    if any(phrase in text for phrase in negative_phrases):
        return "reject"

    return "clarify"


# graph
def build_graph(session):
    
    # Document / MCP
    async def initialize_document(state: State):
        result = await session.call_tool(
            "initialize_file_stream",
            {
                "file_path": state["file_path"],
            },
        )

        data = parse_mcp_json(result)

        if data.get("status") != "success":
            raise RuntimeError(
                data.get(
                    "error",
                    data.get(
                        "message",
                        "MCP initialization failed.",
                    ),
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
                "session_id": state["session_id"],
            },
        )

        data = parse_mcp_json(result)

        return {
            "current_chunk": data.get("current_chunk", []),
            "current_index": 0,
            "has_more": data.get("has_more", False),
        }

    # Kanji
    def select_kanji(state: State):
        kanji = state["current_chunk"][state["current_index"]]

        return {
            "kanji": kanji,
            "quiz_round": 0,
            "quiz_passed": False,
            "quiz_evaluation": None,
        }

    def analyze_kanji(state: State):
        prompt = kanji_generation_prompt(state["kanji"])
        response = structured_kanji_model.invoke(prompt)

        return {"meaning": response}

    def generate_lesson(state: State):
        prompt = lesson_generation_prompt(
            kanji=state["kanji"],
            onyomi=state["meaning"].onyomi,
            kunyomi=state["meaning"].kunyomi,
            kanji_meaning=state["meaning"].kanji_meaning,
        )

        response = structured_lesson_model.invoke(prompt)
        return {"lesson": response}

    def print_lesson(state: State):
        print("\n" + "=" * 60)
        print(f"KANJI: {state['kanji']}")
        print("=" * 60)
        print(state["meaning"].to_polished_string())
        print("\nLesson:")
        print(state["lesson"].to_polished_string())
        print("=" * 60)

    # Quiz readiness HITL
    def quiz_readiness(state: State):
        decision = interrupt({"type": "quiz_readiness","message": f"Are you ready for a quiz testing your knowledge about the kanji {state['kanji']}?"})

        return {"user_decision": decision}

    def route_quiz_readiness(state: State):
        decision = normalize_yes_no(state["user_decision"])

        if decision == "approve":
            return "ready"

        if decision == "reject":
            return "needs_explanation"

        return "clarify"

    # Re-explanation
    def explain_again(state: State):
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a patient Japanese teacher. "
                        "Re-explain the target kanji using the already "
                        "generated kanji information and lesson below. "
                        "Do not contradict the existing information. "
                        "Make the explanation simpler and clearer. "
                        "Focus on the student's likely confusion."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Kanji: {state['kanji']}\n\n"
                        f"Kanji information:\n"
                        f"{state['meaning'].model_dump_json(indent=2)}\n\n"
                        f"Lesson:\n"
                        f"{state['lesson'].model_dump_json(indent=2)}"
                    )
                ),
            ]
        )

        print("\nAdditional Explanation:")
        print(response.content[0]['text'])

        return {
            "messages": [response],
            "quiz_round": 0,
            "quiz_passed": False,
        }

    # Quiz generation
    def generate_quiz_question(state: State):
        prompt = quiz_question_prompt(
            kanji=state["kanji"],
            lesson=state["lesson"].to_polished_string(),
            round_number=state["quiz_round"] + 1,
        )

        # Preserve some recent conversational context
        recent_messages = state["messages"][-6:]

        response = model.invoke([prompt,*recent_messages])

        return {"messages": [response]}

    # Quiz answer HITL
    def wait_for_answer(state: State):
        question_message = state["messages"][-1]
        question = question_message.content[0]['text']

        print("\nQuiz:")
        print(question)

        answer = interrupt({
            "type": "quiz_answer",
            "question": question,
            "kanji": state["kanji"],
        })

        return {"messages": [HumanMessage(content=str(answer))]}

    # Quiz evaluation
    def evaluate_quiz_answer(state: State):
        prompt = SystemMessage(
            content=f"""
You are evaluating a Japanese learner's answer.

Target kanji:
{state["kanji"]}

Kanji information:
{state["meaning"].model_dump_json(indent=2)}

Lesson:
{state["lesson"].model_dump_json(indent=2)}

Evaluate the student's latest answer only.

The student should be evaluated on:
- understanding of the target kanji
- reading accuracy
- meaning
- usage
- relevant Japanese grammar
- whether their answer demonstrates genuine understanding

Be strict but encouraging.

A response can be considered correct even if the wording differs
from an ideal answer, as long as the student's understanding is sound.

Set "mastered" to true only when the student has demonstrated enough
understanding to reasonably move on to the next kanji.

Provide:
1. whether the answer is correct,
2. feedback,
3. an explanation of the correct concept,
4. whether the student has mastered this kanji.
"""
        )

        # The latest two messages are the quiz question + student answer.
        recent_quiz_messages = state["messages"][-2:]

        response = structured_quiz_model.invoke([prompt,*recent_quiz_messages])

        next_round = state["quiz_round"] + 1

        print("\nFeedback:")
        print(response.feedback)

        print("\nExplanation:")
        print(response.explanation)

        return {
            "quiz_evaluation": response,
            "quiz_passed": response.mastered,
            "quiz_round": next_round,
            "messages": [
                AIMessage(
                    content=(
                        f"Feedback: {response.feedback}\n\n"
                        f"Explanation: {response.explanation}"
                    )
                )
            ],
        }

    def route_quiz(state: State):
        evaluation = state["quiz_evaluation"]

        if evaluation.mastered:
            return "quiz_passed"

        if state["quiz_round"] >= MAX_QUIZ_ROUNDS:
            print(
                f"\nMaximum of {MAX_QUIZ_ROUNDS} quiz rounds reached."
            )
            print("Moving on after the review.")
            return "quiz_passed"

        return "next_question"

    # Anki
    def check_anki(state: State):
        exists = check_kanji_exists.invoke({"kanji": state["kanji"],"deck": state["deck"]})
        return {"exists": exists}

    def route_anki(state: State):
        if state["exists"]:
            return "update_approval"

        return "create_approval"

    # Existing-card approval
    def approve_update(state: State):
        decision = interrupt({
            "type": "anki_update_approval",
            "message": (
                f"The kanji {state['kanji']} already exists in "
                f"the Anki deck '{state['deck']}'.\n\n"
                "Do you want to update the existing flashcard "
                "with the newly generated content?"
            )})
        return {"user_decision": decision}

    def route_update_approval(state: State):
        decision = normalize_yes_no(state["user_decision"])

        if decision == "approve":
            return "update"

        if decision == "reject":
            return "skip"

        return "clarify"

    # Update existing Anki card
    def update_flashcard(state: State):
        meaning = state["meaning"]

        result = update_kanji_flashcard.invoke(
            {
                "kanji": state["kanji"],
                "onyomi": meaning.onyomi,
                "kunyomi": meaning.kunyomi,
                "kanji_meaning": meaning.kanji_meaning,
                "deck": state["deck"],
                "onyomi_examples": meaning.onyomi_examples,
                "kunyomi_examples": meaning.kunyomi_examples,
                "lesson": state["lesson"],
            }
        )

        print("\nAnki:")
        print(result)

        return {
            "anki_status": result,
        }

    # New-card approval
    def approve_create(state: State):
        decision = interrupt({"type": "anki_create_approval","message": f"Do you want to add the kanji {state['kanji']} to the Anki deck '{state['deck']}'?"})

        return {"user_decision": decision}

    def route_create_approval(state: State):
        decision = normalize_yes_no(state["user_decision"])

        if decision == "approve":
            return "create"

        if decision == "reject":
            return "skip"

        return "clarify"

    # Create new Anki card
    def create_flashcard(state: State):
        meaning = state["meaning"]

        result = create_kanji_flashcards.invoke(
            {
                "kanji": state["kanji"],
                "onyomi": meaning.onyomi,
                "kunyomi": meaning.kunyomi,
                "kanji_meaning": meaning.kanji_meaning,
                "deck": state["deck"],
                "onyomi_examples": meaning.onyomi_examples,
                "kunyomi_examples": meaning.kunyomi_examples,
                "lesson": state["lesson"],
            }
        )

        print("\nAnki:")
        print(result)

        return {
            "anki_status": result,
        }

    # Move to next kanji
    def advance_kanji(state: State):
        return {
            "current_index": state["current_index"] + 1,
            "quiz_round": 0,
            "quiz_passed": False,
            "quiz_evaluation": None,
            "user_decision": None,
        }

    def route_chunk(state: State):
        if state["current_index"] < len(state["current_chunk"]):
            return "select_kanji"

        return "get_next_chunk"

    def route_document(state: State):
        if state["has_more"]:
            return "select_kanji"

        return "finish"

    # Graph definition
    builder = StateGraph(State)

    # Nodes
    builder.add_node("initialize_document",initialize_document)
    builder.add_node("select_kanji",select_kanji)
    builder.add_node("analyze_kanji",analyze_kanji)
    builder.add_node("generate_lesson",generate_lesson)
    builder.add_node("print_lesson",print_lesson)
    builder.add_node("quiz_readiness",quiz_readiness)
    builder.add_node("explain_again",explain_again)
    builder.add_node("generate_quiz_question",generate_quiz_question)
    builder.add_node("wait_for_answer",wait_for_answer)
    builder.add_node("evaluate_quiz_answer",evaluate_quiz_answer)
    builder.add_node("check_anki",check_anki)
    builder.add_node("approve_update",approve_update)
    builder.add_node("update_flashcard",update_flashcard)
    builder.add_node("approve_create",approve_create)
    builder.add_node("create_flashcard",create_flashcard)
    builder.add_node("advance_kanji",advance_kanji)
    builder.add_node("get_next_chunk",get_next_chunk)

    # Document → Kanji → Lesson
    builder.add_edge(START,"initialize_document")
    builder.add_edge("initialize_document","select_kanji")
    builder.add_edge("select_kanji","analyze_kanji")
    builder.add_edge("analyze_kanji","generate_lesson")
    builder.add_edge("generate_lesson","print_lesson")

    # Quiz readiness
    builder.add_edge("print_lesson","quiz_readiness")
    builder.add_conditional_edges("quiz_readiness",
        route_quiz_readiness,
        {
            "ready": "generate_quiz_question",
            "needs_explanation": "explain_again",
            "clarify": "quiz_readiness",
        })
    builder.add_edge("explain_again","generate_quiz_question")

    # Quiz loop
    builder.add_edge("generate_quiz_question","wait_for_answer")
    builder.add_edge("wait_for_answer","evaluate_quiz_answer")
    builder.add_conditional_edges("evaluate_quiz_answer",
        route_quiz,
        {
            "next_question": "generate_quiz_question",
            "quiz_passed": "check_anki",
        })

    # Anki routing
    builder.add_conditional_edges("check_anki",
        route_anki,
        {
            "update_approval": "approve_update",
            "create_approval": "approve_create",
        })

    # Existing card
    builder.add_conditional_edges("approve_update",
        route_update_approval,
        {
            "update": "update_flashcard",
            "skip": "advance_kanji",
            "clarify": "approve_update",
        })
    builder.add_edge("update_flashcard","advance_kanji")

    # New card
    builder.add_conditional_edges("approve_create",
        route_create_approval,
        {
            "create": "create_flashcard",
            "skip": "advance_kanji",
            "clarify": "approve_create",
        })

    builder.add_edge("create_flashcard","advance_kanji")

    # Document loop
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
    return graph


# Interactive runner
async def run_interactive_graph(graph, initial_state, config):
    """
    Run the graph and resume it whenever an interrupt occurs.
    """

    result = await graph.ainvoke(initial_state,config=config)

    while True:
        interrupts = result.get("__interrupt__")
        if not interrupts:
            return result

        interrupt_value = interrupts[0].value
        print("\n" + "=" * 60)

        if isinstance(interrupt_value, dict):
            print(interrupt_value.get("message", interrupt_value))
        else:
            print(interrupt_value)

        print("=" * 60)
        user_input = input("\n> ").strip()
        result = await graph.ainvoke(Command(resume=user_input),config=config)


# Application entry point
async def run_app():

    current_dir = os.path.dirname(os.path.abspath(__file__))

    server_script_path = os.path.join(current_dir,"mcp_server.py")

    server_params = StdioServerParameters(command=sys.executable,args=[server_script_path])

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            graph = build_graph(session)

            # Use a new thread for every study session.
            thread_id = f"kanji_convo_{uuid.uuid4().hex}"

            config = {"configurable": {"thread_id": thread_id}}

            file_path = input("Enter the path to your Japanese text/PDF file: ").strip()

            final_state = await run_interactive_graph(graph=graph,initial_state={"file_path": file_path,"deck": "Test_Deck1",},config=config)
            print("\nProcessing complete.")

if __name__ == "__main__":
    asyncio.run(run_app())