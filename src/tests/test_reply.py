import asyncio

import pytest

from domain.generation_schema import ReplyIntent
from graph.helpers import HELP_TEXTS, PROMPT_LABELS, hint_for_interrupt, prepass_reply
from graph.nodes import reply as reply_module
from graph.nodes.reply import classify_label
from graph.routing import route_reply_intent, route_tutor_source
from llm.system_prompts import reply_classifier_prompt


@pytest.fixture(autouse=True)
def _isolated_reply_log(tmp_path, monkeypatch):
    monkeypatch.setattr(reply_module, "REPLY_LOG_PATH", tmp_path / "reply_log.jsonl")


def test_prompt_labels_match_spec():
    assert PROMPT_LABELS["quiz_readiness"] == {"ready", "not_ready", "question", "stop", "unclear"}
    assert PROMPT_LABELS["quiz_answer"] == {"answer", "dont_know", "question", "skip_kanji", "stop", "unclear"}
    assert PROMPT_LABELS["anki_approval"] == {"approve", "decline", "question", "stop", "unclear"}


@pytest.mark.parametrize(
    "text,prompt,expected",
    [
        # T7: clean approval
        ("absolutely", "anki_approval", "approve"),
        ("absolutely", "quiz_readiness", "ready"),
        # T8: conditional approval must not match "ok"
        ("ok but only the readings", "anki_approval", "clarify"),
        ("ok but only the readings", "quiz_readiness", "clarify"),
        # commands
        ("stop", "quiz_readiness", "stop"),
        ("stop", "quiz_answer", "stop"),
        ("stop", "anki_approval", "stop"),
        ("quit", "anki_approval", "stop"),
        ("skip", "quiz_answer", "skip_kanji"),
        ("skip this kanji", "quiz_answer", "skip_kanji"),
        ("skip", "quiz_readiness", "clarify"),
        ("skip", "anki_approval", "clarify"),
        # dont_know is answer-prompt only
        ("i don't know", "quiz_answer", "dont_know"),
        ("idk", "quiz_answer", "dont_know"),
        ("i don't know", "anki_approval", "clarify"),
        # readiness / approval polarity
        ("not yet", "quiz_readiness", "not_ready"),
        ("explain again", "quiz_readiness", "not_ready"),
        ("no", "anki_approval", "decline"),
        ("no", "quiz_readiness", "not_ready"),
        # questions: readiness/approval detect directly; quiz answers defer
        # to the classifier so answer attempts always get graded (SPEC 8.2)
        ("what does this mean?", "quiz_answer", "clarify"),
        ("what", "quiz_answer", "clarify"),
        ("help", "quiz_answer", "question"),
        ("why is it read that way?", "quiz_readiness", "question"),
        ("help", "anki_approval", "question"),
        # anything else needs the classifier
        ("maybe later", "quiz_readiness", "clarify"),
        ("...", "quiz_answer", "clarify"),
    ],
)
def test_prepass_reply(text, prompt, expected):
    assert prepass_reply(text, prompt) == expected


def _fake_classifier(label, reason=""):
    class Fake:
        def __init__(self):
            self.calls = 0

        async def ainvoke(self, prompt):
            self.calls += 1
            return ReplyIntent(label=label, reason=reason)

    return Fake()


def test_classify_label_prepass_short_circuits_without_llm():
    for text, prompt, expected in [
        ("absolutely", "anki_approval", "approve"),
        ("stop", "quiz_answer", "stop"),
        ("idk", "quiz_answer", "dont_know"),
    ]:
        fake = _fake_classifier("unclear")
        assert asyncio.run(classify_label(prompt, text, fake)) == expected
        assert fake.calls == 0


def test_classify_label_rogue_coerces_to_unclear():
    fake = _fake_classifier("nuke_the_deck")
    assert asyncio.run(classify_label("anki_approval", "ok but only the readings", fake)) == "unclear"
    assert fake.calls == 1


def test_classify_label_accepts_valid_llm_label():
    fake = _fake_classifier("unclear", reason="conditional approval")
    assert asyncio.run(classify_label("anki_approval", "ok but only the readings", fake)) == "unclear"


def test_classify_label_logs_verdict(tmp_path, monkeypatch):
    import json

    log = tmp_path / "reply_log.jsonl"
    monkeypatch.setattr(reply_module, "REPLY_LOG_PATH", log)
    fake = _fake_classifier("answer")
    assert asyncio.run(classify_label("quiz_answer", "mizu desu", fake)) == "answer"
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["prompt"] == "quiz_answer"
    assert rows[0]["prepass"] == "clarify" and rows[0]["final"] == "answer"


def test_classifier_prompt_lists_allowed_labels():
    for prompt_kind, labels in PROMPT_LABELS.items():
        prompt = reply_classifier_prompt(prompt_kind, "maybe?")
        for label in labels:
            assert label in prompt


@pytest.mark.parametrize(
    "prompt,intent,exists,expected",
    [
        # readiness
        ("quiz_readiness", "ready", False, "generate_quiz_question"),
        ("quiz_readiness", "not_ready", False, "explain_again"),
        ("quiz_readiness", "question", False, "tutor"),
        ("quiz_readiness", "stop", False, "end"),
        ("quiz_readiness", "unclear", False, "quiz_readiness"),
        # answer
        ("quiz_answer", "answer", False, "evaluate_quiz_answer"),
        ("quiz_answer", "dont_know", False, "evaluate_quiz_answer"),
        ("quiz_answer", "question", False, "tutor"),
        ("quiz_answer", "skip_kanji", False, "advance_kanji"),
        ("quiz_answer", "stop", False, "end"),
        ("quiz_answer", "unclear", False, "wait_for_answer"),
        # approval, new and existing cards
        ("anki_approval", "approve", False, "create_flashcard"),
        ("anki_approval", "approve", True, "update_flashcard"),
        ("anki_approval", "decline", False, "advance_kanji"),
        ("anki_approval", "decline", True, "advance_kanji"),
        ("anki_approval", "question", False, "tutor"),
        ("anki_approval", "stop", True, "end"),
        # T8: unclear re-asks the same approval gate
        ("anki_approval", "unclear", False, "approve_create"),
        ("anki_approval", "unclear", True, "approve_update"),
    ],
)
def test_route_reply_intent(prompt, intent, exists, expected):
    state = {"reply_prompt": prompt, "reply_intent": intent, "exists": exists}
    assert route_reply_intent(state) == expected


@pytest.mark.parametrize(
    "prompt,exists,expected",
    [
        ("quiz_readiness", False, "quiz_readiness"),
        ("quiz_answer", False, "wait_for_answer"),
        ("anki_approval", False, "approve_create"),
        ("anki_approval", True, "approve_update"),
    ],
)
def test_route_tutor_source(prompt, exists, expected):
    assert route_tutor_source({"reply_prompt": prompt, "exists": exists}) == expected


@pytest.mark.parametrize(
    "interrupt_type,expected_prompt",
    [
        ("quiz_readiness", "quiz_readiness"),
        ("quiz_answer", "quiz_answer"),
        ("anki_update_approval", "anki_approval"),
        ("anki_create_approval", "anki_approval"),
    ],
)
def test_hint_for_interrupt(interrupt_type, expected_prompt):
    hint = hint_for_interrupt(interrupt_type)
    assert hint == HELP_TEXTS[expected_prompt]
    assert hint


def test_hint_for_unknown_interrupt_is_empty():
    assert hint_for_interrupt("nope") == ""
