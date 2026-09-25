from langchain_core.messages import RemoveMessage
from langgraph.runtime import Runtime

from domain.generation_schema import KanjiOutcome
from graph.context import RuntimeContext
from graph.state import State
from llm.system_prompts import lesson_generation_prompt

async def select_kanji(state: State, runtime: Runtime[RuntimeContext]):
    kanji = state["current_chunk"][state["current_index"]]
    note_ids = await runtime.context.anki.find_notes(kanji)

    notice = None
    if note_ids:
        notice = (
            f"{kanji} is already in your Anki deck. "
            "You will decide about the card after the quiz."
        )

    return {
        "kanji": kanji,
        "messages": [RemoveMessage(id=m.id) for m in state.get("messages", []) if m.id],
        "pending_explanation": notice,
        "exists": len(note_ids) > 0,
        "anki_status": None,
        "current_back": None,
        "dictionary_facts": None,
        "verify_retries": 0,
        "verify_feedback": None,
        "last_reply": None,
        "reply_prompt": None,
        "reply_intent": None,
        "current_question": None,
        "quiz_attempts": [],
        "review_cycles": 0,
    }


def dictionary_lookup(state: State, runtime: Runtime[RuntimeContext]):
    """Verified kanji facts from the local dictionary. No LLM call."""
    facts = runtime.context.dictionary.get_kanji(state["kanji"])

    return {"dictionary_facts": facts}


async def generate_lesson(state: State,runtime: Runtime[RuntimeContext]):
    prompt = lesson_generation_prompt(
        kanji=state["kanji"],
        facts=state["dictionary_facts"],
        feedback=state.get("verify_feedback"),
    )
    response = await runtime.context.models.lesson.ainvoke(prompt)

    return {"lesson": response}


def advance_kanji(state: State):
    results = list(state.get("results") or [])
    kanji = state.get("kanji")
    if kanji and not any(r.kanji == kanji for r in results):
        intent = state.get("reply_intent")
        if intent == "skip_kanji":
            outcome = "skipped"
        elif intent == "decline":
            outcome = "declined"
        else:
            outcome = "passed"
        results.append(KanjiOutcome(kanji=kanji, outcome=outcome))
    return {"current_index": state["current_index"] + 1, "results": results}