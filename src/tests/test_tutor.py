import asyncio
from types import SimpleNamespace

from langchain.messages import AIMessage, HumanMessage

from graph.nodes.quiz import current_question, generate_quiz_question
from graph.nodes.tutor import tutor


def _tutor_state():
    return {
        "kanji": "水",
        "dictionary_facts": None,
        "last_reply": "what does mizu mean?",
    }


def test_current_question_prefers_stored_text_after_tutor():
    from domain.generation_schema import QuizQuestion

    state = {
        "current_question": QuizQuestion(
            type="reading", prompt="What reading is used for 水 alone?", expected="mizu"
        ),
        "messages": [
            AIMessage(content="What reading is used for 水 alone?"),
            HumanMessage(content="what does mizu mean?"),
            AIMessage(content="Mizu means cold water."),
        ],
    }
    assert current_question(state) == "What reading is used for 水 alone?"


def test_current_question_falls_back_to_last_message():
    state = {"messages": [AIMessage(content="What reading is used for 水 alone?")]}
    assert current_question(state) == "What reading is used for 水 alone?"


def test_tutor_leaves_quiz_state_untouched():
    class FakeLLM:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            return AIMessage(content="Mizu means cold water.")

    rt = SimpleNamespace(
        context=SimpleNamespace(dictionary=None, models=SimpleNamespace(llm=FakeLLM()))
    )
    out = asyncio.run(tutor(_tutor_state(), rt))
    assert "quiz_round" not in out
    assert out["pending_explanation"] == "Mizu means cold water."


def test_generate_quiz_question_stores_text():
    from domain.generation_schema import QuizQuestion

    class FakeExaminer:
        async def ainvoke(self, prompt):
            assert "reading" in prompt
            return QuizQuestion(type="reading", prompt="What reading is used for 水 alone?", expected="mizu")

    rt = SimpleNamespace(context=SimpleNamespace(models=SimpleNamespace(examiner=FakeExaminer())))
    state = {
        "kanji": "水",
        "quiz_attempts": [],
        "lesson": SimpleNamespace(
            to_polished_string=lambda: "lesson",
        ),
    }
    out = asyncio.run(generate_quiz_question(state, rt))
    assert out["current_question"].prompt == "What reading is used for 水 alone?"
    assert out["current_question"].expected == "mizu"
    assert "quiz_round" not in out
    assert out["messages"][0].content == "What reading is used for 水 alone?"
