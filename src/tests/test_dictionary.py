from pathlib import Path

import pytest

from infrastructure.dictionary import DictionaryMiss, DictionaryService

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "dictionary.sqlite"

needs_db = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="dictionary DB not built (run: uv run python -m infrastructure.build_dictionary from src/)",
)

# kanji, expected on subset, expected kun subset, expected meaning, strokes
KNOWN_KANJI = [
    ("水", ["スイ"], ["みず"], "water", 4),
    ("日", ["ニチ"], ["ひ"], "day", 4),
    ("友", ["ユウ"], ["とも"], "friend", 4),
    ("火", ["カ"], ["ひ"], "fire", 4),
    ("木", ["モク"], ["き"], "tree", 4),
    ("金", ["キン"], ["かね"], "gold", 8),
    ("土", ["ド"], ["つち"], "earth", 3),
    ("車", ["シャ"], ["くるま"], "car", 7),
    ("学", ["ガク"], ["まな.ぶ"], "study", 8),
    ("語", ["ゴ"], ["かた.る"], "language", 14),
]


@pytest.fixture(scope="module")
def service():
    return DictionaryService(DB_PATH)


@needs_db
@pytest.mark.parametrize("kanji,onyomi,kunyomi,meaning,strokes", KNOWN_KANJI)
def test_get_kanji(service, kanji, onyomi, kunyomi, meaning, strokes):
    facts = service.get_kanji(kanji)
    assert facts.kanji == kanji
    for reading in onyomi:
        assert reading in facts.onyomi, f"{kanji}: {reading} not in {facts.onyomi}"
    for reading in kunyomi:
        assert reading in facts.kunyomi, f"{kanji}: {reading} not in {facts.kunyomi}"
    assert any(meaning in m for m in facts.meanings), facts.meanings
    assert facts.stroke_count == strokes


@needs_db
def test_get_kanji_miss(service):
    with pytest.raises(DictionaryMiss):
        service.get_kanji("A")


@needs_db
def test_lookup_word_hit(service):
    hits = service.lookup_word("水泳")
    assert hits, "expected at least one hit for 水泳"
    assert hits[0].kana == "すいえい"
    assert "swim" in hits[0].meaning


@needs_db
def test_lookup_word_miss(service):
    assert service.lookup_word("不存在XYZ") == []
