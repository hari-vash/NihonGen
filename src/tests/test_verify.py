import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from domain.generation_schema import KanjiLesson
from graph.nodes import verify as V
from graph.nodes.verify import DialogueJudgment, apply_judgments, check_word
from graph.routing import route_verification
from infrastructure.anki import format_verified_words
from infrastructure.dictionary import DictionaryService, WordHit

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "dictionary.sqlite"

needs_db = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="dictionary DB not built (run: uv run python -m infrastructure.build_dictionary from src/)",
)

SUIEI_HITS = [WordHit(word="水泳", kana="すいえい", meaning="swimming")]

DIALOGUE = [
    {"speaker": "Ken", "japanese": "お水をください", "english": "Water, please."},
    {"speaker": "Yuki", "japanese": "水を飲みます", "english": "I drink water."},
]


def make_lesson(words, dialogue=DIALOGUE):
    return KanjiLesson.model_validate(
        {
            "usage_guidelines": {"onyomi_rule": "compounds", "kunyomi_rule": "alone"},
            "words": words,
            "mnemonic": "flowing stream (memory aid)",
            "dialogue": dialogue,
        }
    )


@pytest.fixture(scope="module")
def service():
    return DictionaryService(DB_PATH)


@pytest.fixture()
def runtime(service):
    return SimpleNamespace(
        context=SimpleNamespace(dictionary=service, models=SimpleNamespace(llm=None))
    )


@pytest.fixture()
def isolated_log(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "LOG_PATH", tmp_path / "failures.jsonl")
    return V.LOG_PATH


def test_short_meaning_truncates_glosses():
    from graph.nodes.verify import _short_meaning

    long = "what; you-know-what; that thing; whatsit; penis; dick; hey!"
    assert _short_meaning(long) == "what; you-know-what; that thing"
    assert _short_meaning("swimming") == "swimming"


def test_check_word_valid():
    assert check_word("水", "水泳", "すいえい", SUIEI_HITS) is None


def test_check_word_absent():
    assert check_word("水", "水バナナ", "みずばなな", []) == "not in JMdict"


def test_check_word_wrong_kanji():
    hits = [WordHit(word="電話", kana="でんわ", meaning="telephone")]
    assert check_word("水", "電話", "でんわ", hits) == "does not contain 水"


def test_check_word_wrong_reading():
    assert (
        check_word("水", "水泳", "みずえい", SUIEI_HITS)
        == "reading みずえい not in JMdict (すいえい)"
    )


@needs_db
def test_verify_all_valid(runtime, isolated_log, monkeypatch):
    monkeypatch.setattr(
        V, "judge_dialogue_lines", _judge([False, False])
    )
    state = {
        "kanji": "水",
        "lesson": make_lesson([{"word": "水泳", "kana": "すいえい", "meaning": "learner gloss"}]),
        "verify_retries": 0,
    }
    out = asyncio.run(V.verify_lesson(state, runtime))
    assert out["verify_feedback"] is None
    assert out["verify_retries"] == 0
    word = out["lesson"].words[0]
    assert (word.romaji, word.meaning) == ("suiei", "swimming")
    assert out["lesson"].dialogue[0].romaji == "o mizu wokudasai"


@needs_db
def test_verify_bad_word_retries_without_judge(runtime, isolated_log, monkeypatch):
    def boom(lines, kanji, llm):
        raise AssertionError("judge must be skipped on the retry path")

    monkeypatch.setattr(V, "judge_dialogue_lines", boom)
    state = {
        "kanji": "水",
        "lesson": make_lesson(
            [
                {"word": "水泳", "kana": "すいえい", "meaning": "x"},
                {"word": "水バナナ", "kana": "みずばなな", "meaning": "x"},
            ]
        ),
        "verify_retries": 0,
    }
    out = asyncio.run(V.verify_lesson(state, runtime))
    assert out["verify_retries"] == 1
    assert "水バナナ" in out["verify_feedback"]
    assert "lesson" not in out


@needs_db
def test_verify_exhausted_drops_and_logs(runtime, isolated_log, monkeypatch):
    monkeypatch.setattr(V, "judge_dialogue_lines", _judge([False, False]))
    state = {
        "kanji": "水",
        "lesson": make_lesson(
            [
                {"word": "水泳", "kana": "すいえい", "meaning": "x"},
                {"word": "水バナナ", "kana": "みずばなな", "meaning": "x"},
            ]
        ),
        "verify_retries": 2,
    }
    out = asyncio.run(V.verify_lesson(state, runtime))
    assert [w.word for w in out["lesson"].words] == ["水泳"]
    assert out["verify_feedback"] is None
    rows = [
        json.loads(line) for line in isolated_log.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["word"] == "水バナナ" and rows[0]["retries"] == 2


@needs_db
def test_verify_all_dropped_proceeds_empty(runtime, isolated_log, monkeypatch):
    monkeypatch.setattr(V, "judge_dialogue_lines", _judge([False, False]))
    state = {
        "kanji": "水",
        "lesson": make_lesson([{"word": "水バナナ", "kana": "みずばなな", "meaning": "x"}]),
        "verify_retries": 2,
    }
    out = asyncio.run(V.verify_lesson(state, runtime))
    assert out["lesson"].words == []
    assert out["verify_feedback"] is None


@needs_db
def test_verify_judge_flags_dropped_and_logged(runtime, isolated_log, monkeypatch):
    monkeypatch.setattr(
        V, "judge_dialogue_lines", _judge([False, True], reasons=["", "EN does not match JP"])
    )
    state = {
        "kanji": "水",
        "lesson": make_lesson([{"word": "水泳", "kana": "すいえい", "meaning": "x"}]),
        "verify_retries": 0,
    }
    out = asyncio.run(V.verify_lesson(state, runtime))
    assert [line.speaker for line in out["lesson"].dialogue] == ["Ken"]
    log_text = isolated_log.read_text(encoding="utf-8")
    assert "dialogue flagged: EN does not match JP" in log_text


def test_apply_judgments_pure():
    lesson = make_lesson([], DIALOGUE)
    kept, flagged = apply_judgments(
        lesson, [DialogueJudgment(flagged=True, reason="r"), DialogueJudgment(flagged=False)]
    )
    assert [line.speaker for line in kept.dialogue] == ["Yuki"]
    assert len(flagged) == 1 and flagged[0][1] == "r"


def test_apply_judgments_misaligned_raises():
    lesson = make_lesson([], DIALOGUE)
    with pytest.raises(AssertionError):
        apply_judgments(lesson, [DialogueJudgment(flagged=False)])


def test_route_verification():
    assert route_verification({"verify_feedback": "retry me"}) == "retry"
    assert route_verification({"verify_feedback": None}) == "verified"


def test_format_verified_words():
    from domain.generation_schema import VerifiedWord

    words = [VerifiedWord(word="水泳", kana="すいえい", meaning="swimming", romaji="suiei")]
    assert format_verified_words(words) == "- 水泳 [すいえい] (suiei) - swimming"
    assert format_verified_words([]) == ""


def _judge(flags, reasons=None):
    reasons = reasons or [""] * len(flags)

    async def fake(lines, kanji, llm):
        return [
            DialogueJudgment(flagged=f, reason=r) for f, r in zip(flags, reasons)
        ]

    return fake
