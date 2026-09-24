import asyncio

import pytest

from domain.generation_schema import ReplyIntent
from graph.helpers import PROMPT_LABELS, normalize_yes_no, prepass_reply
from graph.nodes.reply import classify_label
from llm.system_prompts import reply_classifier_prompt


def test_normalize_yes_no_unchanged():
    assert normalize_yes_no("absolutely") == "approve"
    assert normalize_yes_no("nope") == "reject"
    assert normalize_yes_no("ok but only the readings") == "clarify"


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
        # questions
        ("what does this mean?", "quiz_answer", "question"),
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


def test_classifier_prompt_lists_allowed_labels():
    for prompt_kind, labels in PROMPT_LABELS.items():
        prompt = reply_classifier_prompt(prompt_kind, "maybe?")
        for label in labels:
            assert label in prompt
