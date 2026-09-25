from graph.nodes.quiz import MAX_REVIEW_CYCLES, mastery_gate
from graph.state import State


def _approval_target(state: State):
    return "approve_update" if state.get("exists") else "approve_create"


def route_reply_intent(state: State):
    """Single router for all classified replies. Reads (reply_prompt, reply_intent)."""
    prompt = state.get("reply_prompt")
    intent = state.get("reply_intent")

    if prompt == "quiz_readiness":
        return {
            "ready": "generate_quiz_question",
            "not_ready": "explain_again",
            "question": "tutor",
            "stop": "end",
            "unclear": "quiz_readiness",
        }.get(intent, "quiz_readiness")

    if prompt == "quiz_answer":
        return {
            "answer": "evaluate_quiz_answer",
            "dont_know": "evaluate_quiz_answer",
            "question": "tutor",
            "skip_kanji": "advance_kanji",
            "stop": "end",
            "unclear": "wait_for_answer",
        }.get(intent, "wait_for_answer")

    if prompt == "anki_approval":
        if intent == "approve":
            return "update_flashcard" if state.get("exists") else "create_flashcard"
        return {
            "decline": "advance_kanji",
            "question": "tutor",
            "stop": "end",
            "unclear": _approval_target(state),
        }.get(intent, _approval_target(state))

    return "end"


def route_tutor_source(state: State):
    """Send the tutor back to the prompt that asked the question."""
    prompt = state.get("reply_prompt")
    if prompt == "quiz_answer":
        return "wait_for_answer"
    if prompt == "anki_approval":
        return _approval_target(state)
    return "quiz_readiness"


def route_quiz(state: State):
    """Thin reader over the mastery gate (SPEC 8.1). Fail with review cycles
    left goes back for re-explanation; exhausted cycles park the kanji."""
    verdict = mastery_gate(state.get("quiz_attempts") or [])

    if verdict == "pass":
        return "quiz_passed"

    if verdict == "fail":
        if (state.get("review_cycles") or 0) >= MAX_REVIEW_CYCLES:
            return "park"
        return "needs_review"

    return "next_question"


def route_anki(state: State):
    if state["exists"]:
        return "update_approval"

    return "create_approval"


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


def route_verification(state: State):
    if state.get("verify_feedback"):
        return "retry"

    return "verified"


def route_input(state: State):
    if state.get("input_mode") == "typed":
        return "typed_input"

    if state.get("input_mode") == "document":
        return "initialize_document"

    return "finish"