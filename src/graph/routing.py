from graph.helpers import normalize_yes_no
from graph.state import State


MAX_QUIZ_ROUNDS = 6


def route_quiz_readiness(state: State):
    decision = normalize_yes_no(state["user_decision"])

    if decision == "approve":
        return "ready"

    if decision == "reject":
        return "needs_explanation"

    return "clarify"


def route_quiz(state: State):
    evaluation = state["quiz_evaluation"]

    if evaluation.mastered:
        return "quiz_passed"

    if state["quiz_round"] >= MAX_QUIZ_ROUNDS:
        return "needs_review"

    return "next_question"


def route_anki(state: State):
    if state["exists"]:
        return "update_approval"

    return "create_approval"


def route_update_approval(state: State):
    decision = normalize_yes_no(state["user_decision"])

    if decision == "approve":
        return "update"

    if decision == "reject":
        return "skip"

    return "clarify"


def route_create_approval(state: State):
    decision = normalize_yes_no(state["user_decision"])

    if decision == "approve":
        return "create"

    if decision == "reject":
        return "skip"

    return "clarify"


def route_chunk(state: State):
    if state["current_index"] < len(state["current_chunk"]):
        return "select_kanji"

    if state["has_more"]:
        return "get_next_chunk"

    return "finish"


def route_document(state: State):
    if len(state.get("current_chunk") or []) > 0:
        return "select_kanji"

    return "finish"