import asyncio
from types import SimpleNamespace

import pytest

from domain.generation_schema import QuizAttempt, QuizGrade, QuizQuestion
from graph.nodes.quiz import allowed_types, current_question, evaluate_quiz_answer


def _q(qtype="reading", prompt="Q?", expected="A"):
    return QuizQuestion(type=qtype, prompt=prompt, expected=expected)


def _attempt(qtype="reading", outcome="correct"):
    return QuizAttempt(question=_q(qtype), user_answer="x", outcome=outcome, feedback="f")


def test_allowed_types_open_early():
    assert set(allowed_types([])) == {
        "reading", "meaning", "word_reading", "word_meaning",
        "in_context_reading", "onkun_choice",
    }
    assert len(allowed_types([_attempt("reading")])) == 6


def test_allowed_types_force_missing_family_on_last():
    attempts = [_attempt("reading"), _attempt("onkun_choice"), _attempt("word_reading"), _attempt("reading")]
    assert set(allowed_types(attempts)) == {"meaning", "word_meaning"}


def test_allowed_types_force_reading_when_absent():
    attempts = [_attempt("meaning"), _attempt("word_meaning"), _attempt("meaning"), _attempt("word_meaning")]
    got = allowed_types(attempts)
    assert got and all(t in {"reading", "onkun_choice", "in_context_reading", "word_reading"} for t in got)


def test_allowed_types_satisfied_stays_open():
    attempts = [_attempt("reading"), _attempt("meaning"), _attempt("reading"), _attempt("meaning")]
    assert len(allowed_types(attempts)) == 6


def test_mastery_gate_early_fail_on_fourth():
    from graph.nodes.quiz import mastery_gate

    assert mastery_gate([_attempt("reading", o) for o in ("correct", "miss", "miss", "miss")]) == "fail"
    assert mastery_gate([_attempt("reading", o) for o in ("miss", "miss", "correct", "miss")]) == "fail"
    assert mastery_gate([_attempt("reading", o) for o in ("correct", "correct", "miss", "miss")]) == "continue"


def test_t9_full_walk_review_review_park():
    import asyncio
    from types import SimpleNamespace

    from langchain.messages import AIMessage

    from graph.nodes.quiz import explain_again, park_kanji
    from graph.routing import route_quiz

    class FakeLLM:
        async def ainvoke(self, messages):
            return AIMessage(content="Simpler take.")

    def run_explain(state):
        rt = SimpleNamespace(context=SimpleNamespace(models=SimpleNamespace(llm=FakeLLM())))
        return asyncio.run(explain_again(state, rt))

    base = {
        "kanji": "水",
        "dictionary_facts": SimpleNamespace(model_dump_json=lambda indent=0: "{}"),
        "lesson": SimpleNamespace(model_dump_json=lambda indent=0: "{}"),
    }
    failed = [_attempt("reading", "miss")] * 3

    # cycle 1
    assert route_quiz({"quiz_attempts": failed, "review_cycles": 0}) == "needs_review"
    out = run_explain({**base, "quiz_attempts": failed, "review_cycles": 0})
    assert out["review_cycles"] == 1 and out["quiz_attempts"] == []

    # cycle 2
    assert route_quiz({"quiz_attempts": failed, "review_cycles": 1}) == "needs_review"
    out = run_explain({**base, "quiz_attempts": failed, "review_cycles": 1})
    assert out["review_cycles"] == 2 and out["quiz_attempts"] == []

    # parked, no Anki keys
    assert route_quiz({"quiz_attempts": failed, "review_cycles": 2}) == "park"
    parked = park_kanji({"kanji": "水"})
    assert set(parked) == {"pending_explanation"}


def test_quiz_passed_requires_gate_pass_sweep():
    import itertools

    from graph.nodes.quiz import mastery_gate
    from graph.routing import route_quiz

    for n in range(6):
        for outcomes in itertools.product("CM", repeat=n):
            attempts = [
                _attempt("reading", "correct" if o == "C" else "miss") for o in outcomes
            ]
            assert (route_quiz({"quiz_attempts": attempts}) == "quiz_passed") == (
                mastery_gate(attempts) == "pass"
            )


def test_mastery_gate_matrix():
    from graph.nodes.quiz import mastery_gate

    all_correct = [_attempt("reading", "correct") for _ in range(5)]
    assert mastery_gate(all_correct) == "pass"

    mixed_pass = [_attempt("reading", "correct")] * 3 + [
        _attempt("meaning", "miss"),
        _attempt("reading", "dont_know"),
    ]
    assert mastery_gate(mixed_pass) == "pass"

    three_misses = [_attempt("reading", "correct")] * 2 + [_attempt("meaning", "miss")] * 3
    assert mastery_gate(three_misses) == "fail"

    early_fail = [_attempt("reading", "miss")] * 3
    assert mastery_gate(early_fail) == "fail"

    assert mastery_gate([]) == "continue"
    assert mastery_gate([_attempt("reading", "correct")] * 4) == "continue"
    assert mastery_gate([_attempt("reading", "miss")] * 2) == "continue"


def test_mastery_gate_dont_know_counts_as_miss():
    from graph.nodes.quiz import mastery_gate

    attempts = [_attempt("reading", "dont_know")] * 2 + [_attempt("meaning", "miss")]
    assert mastery_gate(attempts) == "fail"


def test_route_quiz_delegates_to_gate():
    from graph.routing import route_quiz

    assert route_quiz({"quiz_attempts": [_attempt("reading", "correct")] * 5}) == "quiz_passed"
    assert route_quiz({"quiz_attempts": [_attempt("reading", "miss")] * 3}) == "needs_review"
    assert route_quiz({"quiz_attempts": [_attempt()]}) == "next_question"
    assert route_quiz({}) == "next_question"


def test_route_quiz_parks_when_cycles_exhausted():
    from graph.routing import route_quiz

    failed = [_attempt("reading", "miss")] * 3
    assert route_quiz({"quiz_attempts": failed, "review_cycles": 1}) == "needs_review"
    assert route_quiz({"quiz_attempts": failed, "review_cycles": 2}) == "park"


def test_explain_again_consumes_cycle_only_after_attempts():
    from graph.nodes.quiz import explain_again

    class FakeLLM:
        def __init__(self):
            self.system = ""

        async def ainvoke(self, messages):
            self.system = messages[0].content
            from langchain.messages import AIMessage

            return AIMessage(content="Simpler take.")

    async def run(state):
        rt = SimpleNamespace(
            context=SimpleNamespace(models=SimpleNamespace(llm=FakeLLM()))
        )
        return await explain_again(state, rt), rt.context.models.llm.system

    base = {
        "kanji": "水",
        "dictionary_facts": SimpleNamespace(model_dump_json=lambda indent=0: "{}"),
        "lesson": SimpleNamespace(model_dump_json=lambda indent=0: "{}"),
    }
    probe = _attempt("reading", "miss")
    out, system = asyncio.run(
        run({**base, "quiz_attempts": [probe], "review_cycles": 0})
    )
    assert out["review_cycles"] == 1
    assert out["quiz_attempts"] == []
    assert "You answered:" in system

    out, _ = asyncio.run(run({**base, "quiz_attempts": [], "review_cycles": 0}))
    assert out["review_cycles"] == 0


def test_park_kanji_notice_without_anki():
    from graph.nodes.quiz import park_kanji

    out = park_kanji({"kanji": "水"})
    assert "Parked 水" in out["pending_explanation"]
    assert set(out) == {"pending_explanation"}


def test_select_kanji_resets_cycles_and_clears_messages():
    from langchain.messages import AIMessage, HumanMessage

    from graph.nodes.kanji import select_kanji

    out = select_kanji(
        {
            "current_chunk": ["水"],
            "current_index": 0,
            "messages": [AIMessage(content="a", id="1"), HumanMessage(content="b", id="2")],
        }
    )
    assert out["review_cycles"] == 0
    assert out["quiz_attempts"] == []
    assert out["current_question"] is None
    removals = out["messages"]
    assert {m.id for m in removals} == {"1", "2"}
    assert all(type(m).__name__ == "RemoveMessage" for m in removals)


def test_generate_quiz_question_retries_defiant_type():
    from graph.nodes.quiz import generate_quiz_question

    calls = {"n": 0}

    class DefiantOnce:
        async def ainvoke(self, prompt):
            calls["n"] += 1
            if calls["n"] == 1:
                return _q("reading", "Q1?", "A")
            return _q("meaning", "Q2?", "A")

    rt = SimpleNamespace(
        context=SimpleNamespace(models=SimpleNamespace(examiner=DefiantOnce()))
    )
    state = {
        "kanji": "水",
        "lesson": SimpleNamespace(to_polished_string=lambda: "L"),
        "quiz_attempts": [_attempt("reading"), _attempt("reading"), _attempt("reading"), _attempt("reading")],
    }
    out = asyncio.run(generate_quiz_question(state, rt))
    assert calls["n"] == 2
    assert out["current_question"].type == "meaning"


def test_current_question_reads_structured():
    state = {
        "current_question": _q(prompt="Structured?"),
        "messages": [],
    }
    assert current_question(state) == "Structured?"


def _runtime(grader=None):
    class FakeLLM:
        def with_structured_output(self, model, method=None):
            assert model is QuizGrade
            return grader

    return SimpleNamespace(context=SimpleNamespace(models=SimpleNamespace(llm=FakeLLM())))


def test_evaluate_dont_know_skips_llm():
    class Boom:
        def with_structured_output(self, model, method=None):
            raise AssertionError("dont_know must not call the LLM")

    rt = SimpleNamespace(context=SimpleNamespace(models=SimpleNamespace(llm=Boom())))
    state = {
        "kanji": "水",
        "current_question": _q(prompt="Q?", expected="mizu"),
        "last_reply": "i don't know",
        "reply_intent": "dont_know",
        "quiz_attempts": [],
    }
    out = asyncio.run(evaluate_quiz_answer(state, rt))
    attempt = out["quiz_attempts"][0]
    assert attempt.outcome == "dont_know"
    assert "mizu" in attempt.feedback
    assert attempt.question.expected == "mizu"
    assert out["current_question"] is None


def test_evaluate_grades_and_echoes_question():
    class Grader:
        def __init__(self):
            self.prompts = []

        async def ainvoke(self, prompt):
            self.prompts.append(prompt)
            assert "mizu" in prompt
            return QuizGrade(outcome="correct", feedback="Nailed it.")

    grader = Grader()
    state = {
        "kanji": "水",
        "current_question": _q(prompt="Q?", expected="mizu"),
        "last_reply": "mizu",
        "reply_intent": "answer",
        "quiz_attempts": [_attempt()],
    }
    out = asyncio.run(evaluate_quiz_answer(state, _runtime(grader)))
    assert len(out["quiz_attempts"]) == 2
    attempt = out["quiz_attempts"][1]
    assert attempt.outcome == "correct"
    assert attempt.user_answer == "mizu"
    assert attempt.question.prompt == "Q?"
    assert "mizu" in grader.prompts[0]


def test_evaluate_appends_without_mutating():
    before = [_attempt()]

    class Grader:
        async def ainvoke(self, prompt):
            return QuizGrade(outcome="miss", feedback="Try again: A.")

    state = {
        "kanji": "水",
        "current_question": _q(expected="A"),
        "last_reply": "B",
        "reply_intent": "answer",
        "quiz_attempts": before,
    }
    out = asyncio.run(evaluate_quiz_answer(state, _runtime(Grader())))
    assert len(before) == 1 and len(out["quiz_attempts"]) == 2
