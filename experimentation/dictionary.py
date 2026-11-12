"""Read-only access to the local dictionary (KANJIDIC2 + JMdict subset)."""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from schemas import KanjiFacts

DICT_PATH = Path(__file__).resolve().parents[1] / "data" / "dictionary.sqlite"


class DictionaryMiss(LookupError):
    """Raised when a kanji has no entry. Never treated as success."""

    def __init__(self, kanji: str):
        super().__init__(f"No dictionary entry for kanji {kanji!r}")
        self.kanji = kanji


@dataclass(frozen=True, slots=True)
class WordHit:
    word: str
    kana: str
    meaning: str


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DICT_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def assert_dictionary_available() -> None:
    """Fail loudly at startup if the DB is missing or unreadable."""
    if not DICT_PATH.exists():
        raise FileNotFoundError(
            f"Dictionary DB not found at {DICT_PATH}. "
            "Run: uv run python -m infrastructure.build_dictionary (from src/)"
        )
    with closing(_connect()) as conn:
        conn.execute("SELECT 1 FROM kanji LIMIT 1").fetchone()


def lookup_kanji(kanji: str) -> KanjiFacts:
    """Exact lookup by kanji literal. Raises DictionaryMiss when absent."""
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT kanji, onyomi, kunyomi, meanings, stroke_count, grade"
            " FROM kanji WHERE kanji = ?",
            (kanji,),
        ).fetchone()

    if row is None:
        raise DictionaryMiss(kanji)

    return KanjiFacts(
        kanji=row["kanji"],
        onyomi=json.loads(row["onyomi"]),
        kunyomi=json.loads(row["kunyomi"]),
        meanings=json.loads(row["meanings"]),
        stroke_count=row["stroke_count"],
        grade=row["grade"],
    )


def lookup_word(word: str, limit: int = 5) -> list[WordHit]:
    """Exact-match word lookup. Returns [] when absent (advisory, not fatal)."""
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT word, kana, meaning FROM words WHERE word = ? LIMIT ?",
            (word, limit),
        ).fetchall()

    return [WordHit(word=r["word"], kana=r["kana"], meaning=r["meaning"]) for r in rows]
