from langgraph.runtime import Runtime

from graph.context import RuntimeContext
from graph.state import State
from llm.system_prompts import lesson_generation_prompt

def select_kanji(state: State):
    kanji = state["current_chunk"][state["current_index"]]

    return {
        "kanji": kanji,
        "pending_explanation": None,
        "anki_status": None,
        "dictionary_facts": None,
        "verify_retries": 0,
        "verify_feedback": None,
        "last_reply": None,
        "reply_prompt": None,
        "reply_intent": None,
        "current_question": None,
        "quiz_attempts": [],
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
    return {"current_index": state["current_index"] + 1}