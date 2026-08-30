from langgraph.runtime import Runtime

from graph.context import RuntimeContext
from graph.state import State
from llm.system_prompts import kanji_generation_prompt,lesson_generation_prompt

def select_kanji(state: State):
    kanji = state["current_chunk"][state["current_index"]]

    return {"kanji": kanji,"quiz_round": 0}


async def analyze_kanji(state: State,runtime: Runtime[RuntimeContext]):
    prompt = kanji_generation_prompt(state["kanji"])
    response = await runtime.context.models.kanji.ainvoke(prompt)

    return {"kanji_info": response}


async def generate_lesson(state: State,runtime: Runtime[RuntimeContext]):
    kanji_info = state["kanji_info"]
    prompt = lesson_generation_prompt(
        kanji=state["kanji"],
        onyomi=kanji_info.onyomi,
        kunyomi=kanji_info.kunyomi,
        kanji_meaning=kanji_info.kanji_meaning,
    )
    response = await runtime.context.models.lesson.ainvoke(prompt)

    return {"lesson": response}


def advance_kanji(state: State):
    return {"current_index": state["current_index"] + 1}


def print_lesson(state: State):
    print("\n" + "=" * 60)
    print(f"KANJI: {state['kanji']}")
    print("=" * 60)
    print(state["kanji_info"].to_polished_string())
    print("\nLesson:")
    print(state["lesson"].to_polished_string())
    print("=" * 60)
    return {}