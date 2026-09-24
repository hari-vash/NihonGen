import pytest

from graph.helpers import PROMPT_LABELS, normalize_yes_no, prepass_reply


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
