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
