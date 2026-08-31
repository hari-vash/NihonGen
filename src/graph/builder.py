from langgraph.graph import END, START, StateGraph
from graph.context import RuntimeContext

from graph.nodes.anki import approve_create,approve_update,check_anki,create_flashcard,update_flashcard
from graph.nodes.document import get_next_chunk, initialize_document
from graph.nodes.kanji import advance_kanji,analyze_kanji,generate_lesson,print_lesson,select_kanji
from graph.nodes.quiz import evaluate_quiz_answer,explain_again,generate_quiz_question,quiz_readiness,wait_for_answer
from graph.routing import route_anki,route_chunk,route_create_approval,route_document,route_quiz,route_quiz_readiness,route_update_approval
from graph.state import State
from graph.checkpointer import create_checkpointer


def build_graph(*, checkpointer=None):
    builder = StateGraph(
        State,
        context_schema=RuntimeContext,
    )

    # Document → Kanji → Lesson
    builder.add_node("initialize_document", initialize_document)
    builder.add_node("select_kanji", select_kanji)
    builder.add_node("analyze_kanji", analyze_kanji)
    builder.add_node("generate_lesson", generate_lesson)
    builder.add_node("print_lesson", print_lesson)

    builder.add_edge(START, "initialize_document")
    builder.add_edge("initialize_document", "select_kanji")
    builder.add_edge("select_kanji", "analyze_kanji")
    builder.add_edge("analyze_kanji", "generate_lesson")
    builder.add_edge("generate_lesson", "print_lesson")

    # Quiz readiness
    builder.add_node("quiz_readiness", quiz_readiness)
    builder.add_node("explain_again", explain_again)
    builder.add_edge("print_lesson", "quiz_readiness")
    builder.add_conditional_edges("quiz_readiness",
        route_quiz_readiness,
        {
            "ready": "generate_quiz_question",
            "needs_explanation": "explain_again",
            "clarify": "quiz_readiness",
        })
    builder.add_edge("explain_again", "generate_quiz_question")

    # Quiz loop
    builder.add_node("generate_quiz_question", generate_quiz_question)
    builder.add_node("wait_for_answer", wait_for_answer)
    builder.add_node("evaluate_quiz_answer", evaluate_quiz_answer)
    builder.add_edge("generate_quiz_question", "wait_for_answer")
    builder.add_edge("wait_for_answer", "evaluate_quiz_answer")
    builder.add_conditional_edges("evaluate_quiz_answer",
        route_quiz,
        {
            "next_question": "generate_quiz_question",
            "needs_review": "explain_again",
            "quiz_passed": "check_anki",
        })

    # Anki
    builder.add_node("check_anki", check_anki)
    builder.add_node("approve_update", approve_update)
    builder.add_node("update_flashcard", update_flashcard)
    builder.add_node("approve_create", approve_create)
    builder.add_node("create_flashcard", create_flashcard)
    builder.add_conditional_edges("check_anki",
        route_anki,
        {
            "update_approval": "approve_update",
            "create_approval": "approve_create",
        })
    builder.add_conditional_edges("approve_update",
        route_update_approval,
        {
            "update": "update_flashcard",
            "skip": "advance_kanji",
            "clarify": "approve_update",
        })
    builder.add_edge("update_flashcard", "advance_kanji")
    builder.add_conditional_edges("approve_create",
        route_create_approval,
        {
            "create": "create_flashcard",
            "skip": "advance_kanji",
            "clarify": "approve_create",
        })
    builder.add_edge("create_flashcard", "advance_kanji")

    # Document progression
    builder.add_node("advance_kanji", advance_kanji)
    builder.add_node("get_next_chunk", get_next_chunk)
    builder.add_conditional_edges("advance_kanji",
        route_chunk,
        {
            "select_kanji": "select_kanji",
            "get_next_chunk": "get_next_chunk",
            "finish": END,
        })

    builder.add_conditional_edges("get_next_chunk",
        route_document,
        {
            "select_kanji": "select_kanji",
            "finish": END,
        })

    # Compile
    if checkpointer is None:
        checkpointer = create_checkpointer()

    return builder.compile(checkpointer=checkpointer)