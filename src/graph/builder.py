from langgraph.graph import END, START, StateGraph
from graph.context import RuntimeContext

from graph.nodes.anki import approve_create,approve_update,check_anki,create_flashcard,update_flashcard
from graph.nodes.document import get_next_chunk, initialize_document
from graph.nodes.kanji import advance_kanji,dictionary_lookup,generate_lesson,select_kanji
from graph.nodes.quiz import evaluate_quiz_answer,explain_again,generate_quiz_question,quiz_readiness,wait_for_answer
from graph.nodes.reply import classify_reply
from graph.nodes.tutor import tutor
from graph.nodes.verify import verify_lesson
from graph.routing import route_anki,route_chunk,route_document,route_quiz,route_reply_intent,route_tutor_source,route_verification
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
    builder.add_node("dictionary_lookup", dictionary_lookup)
    builder.add_node("generate_lesson", generate_lesson)
    builder.add_node("verify_lesson", verify_lesson)

    builder.add_edge(START, "initialize_document")
    builder.add_edge("initialize_document", "select_kanji")
    builder.add_edge("select_kanji", "dictionary_lookup")
    builder.add_edge("dictionary_lookup", "generate_lesson")
    builder.add_edge("generate_lesson", "verify_lesson")
    builder.add_conditional_edges("verify_lesson",
        route_verification,
        {
            "verified": "quiz_readiness",
            "retry": "generate_lesson",
        })

    # Quiz readiness
    builder.add_node("quiz_readiness", quiz_readiness)
    builder.add_node("explain_again", explain_again)
    builder.add_node("classify_reply", classify_reply)
    builder.add_node("tutor", tutor)
    builder.add_edge("quiz_readiness", "classify_reply")
    builder.add_edge("wait_for_answer", "classify_reply")
    builder.add_edge("approve_create", "classify_reply")
    builder.add_edge("approve_update", "classify_reply")
    builder.add_conditional_edges("classify_reply",
        route_reply_intent,
        {
            "generate_quiz_question": "generate_quiz_question",
            "explain_again": "explain_again",
            "evaluate_quiz_answer": "evaluate_quiz_answer",
            "advance_kanji": "advance_kanji",
            "create_flashcard": "create_flashcard",
            "update_flashcard": "update_flashcard",
            "quiz_readiness": "quiz_readiness",
            "wait_for_answer": "wait_for_answer",
            "approve_create": "approve_create",
            "approve_update": "approve_update",
            "tutor": "tutor",
            "end": END,
        })
    builder.add_conditional_edges("tutor",
        route_tutor_source,
        {
            "quiz_readiness": "quiz_readiness",
            "wait_for_answer": "wait_for_answer",
            "approve_create": "approve_create",
            "approve_update": "approve_update",
        })
    builder.add_edge("explain_again", "generate_quiz_question")

    # Quiz loop
    builder.add_node("generate_quiz_question", generate_quiz_question)
    builder.add_node("wait_for_answer", wait_for_answer)
    builder.add_node("evaluate_quiz_answer", evaluate_quiz_answer)
    builder.add_edge("generate_quiz_question", "wait_for_answer")
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
    builder.add_edge("update_flashcard", "advance_kanji")
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