import asyncio
from types import SimpleNamespace

from application import renderer
from application.channel import FakeChannel
from application.runner import run_interactive_graph
from domain.generation_schema import AnkiResult, KanjiFacts, KanjiLesson, QuizAttempt, QuizQuestion


def _facts():
    return KanjiFacts(
        kanji="水", onyomi=["スイ"], kunyomi=["みず"],
        meanings=["water"], stroke_count=4, grade=1,
    )


def _lesson():
    return KanjiLesson.model_validate(
        {
            "usage_guidelines": {"onyomi_rule": "c", "kunyomi_rule": "a"},
            "words": [{"word": "水泳", "kana": "すいえい", "meaning": "swimming", "romaji": "suiei"}],
            "mnemonic": "stream",
            "dialogue": [],
        }
    )


def test_renderer_returns_strings_silently(capsys):
    attempt = QuizAttempt(
        question=QuizQuestion(type="reading", prompt="Q?", expected="A"),
        user_answer="A",
        outcome="correct",
        feedback="good",
    )
    outputs = [
        renderer.render_kanji("水"),
        renderer.render_kanji_info(_facts()),
        renderer.render_kanji_lesson(_lesson()),
        renderer.render_quiz_result(attempt),
        renderer.render_anki_result(AnkiResult(ok=True, action="created", message="done")),
        renderer.render_summary([]),
        renderer.render_additional_explanation("extra"),
        renderer.render_interrupt({"message": "ready?", "question": "Q?"}),
    ]
    assert all(isinstance(text, str) and text for text in outputs)
    assert "KANJI: 水" in outputs[0]
    assert "スイ" in outputs[1] and "水泳" in outputs[2]
    assert "good" in outputs[3] and "created" in outputs[4]
    assert "No kanji completed" in outputs[5]
    assert capsys.readouterr().out == ""


def test_run_interactive_graph_through_fake_channel():
    interrupt_state = {
        "kanji": "水",
        "dictionary_facts": _facts(),
        "lesson": _lesson(),
        "__interrupt__": [SimpleNamespace(value={"message": "ready?", "type": "quiz_readiness"})],
    }
    final_state = {"kanji": "水", "results": []}

    class FakeGraph:
        def __init__(self):
            self.resumes = []

        async def ainvoke(self, *args, **kwargs):
            from langgraph.types import Command

            if args and isinstance(args[0], Command):
                self.resumes.append(args[0].resume)
                return final_state
            return interrupt_state

    channel = FakeChannel(replies=["yes"])
    graph = FakeGraph()
    out = asyncio.run(
        run_interactive_graph(graph, {}, {}, SimpleNamespace(), channel)
    )
    assert out == final_state
    assert graph.resumes == ["yes"]
    joined = "\n".join(channel.sent)
    assert "KANJI: 水" in joined and "ready?" in joined


def _attempt(text):
    return SimpleNamespace(feedback=text, outcome="miss", question=SimpleNamespace(expected="X"))


def test_feedback_renders_after_attempts_reset():
    first = {"kanji": "水", "quiz_attempts": [_attempt("one"), _attempt("two"), _attempt("three")],
             "__interrupt__": [SimpleNamespace(value={"message": "q?"})]}
    second = {"kanji": "水", "quiz_attempts": [_attempt("four")],
              "__interrupt__": [SimpleNamespace(value={"message": "q?"})]}
    final_state = {"kanji": "水", "results": []}

    class FakeGraph:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, *args, **kwargs):
            from langgraph.types import Command

            self.calls += 1
            if self.calls == 1:
                return first
            if self.calls == 2:
                return second
            return final_state

    channel = FakeChannel(replies=["a", "b"])
    asyncio.run(run_interactive_graph(FakeGraph(), {}, {}, SimpleNamespace(), channel))
    joined = "\n".join(channel.sent)
    assert "three" in joined and "four" in joined


def test_terminal_pending_renders_before_summary():
    final_state = {"kanji": "水", "pending_explanation": "Parked 水: done.", "results": []}

    class FakeGraph:
        async def ainvoke(self, *args, **kwargs):
            return final_state

    channel = FakeChannel(replies=[])
    asyncio.run(run_interactive_graph(FakeGraph(), {}, {}, SimpleNamespace(), channel))
    joined = "\n".join(channel.sent)
    assert "Parked 水: done." in joined
    assert joined.index("Parked 水: done.") < joined.index("Session summary:")
