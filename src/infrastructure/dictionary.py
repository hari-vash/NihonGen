"""Local EDRDG dictionary gateway. Read-only, no network at runtime.

All kanji facts come from ``data/dictionary.sqlite`` (built by
``infrastructure/build_dictionary.py``). The LLM never authors readings.

//docs/SPEC.md: FR-5, section 6 (DictionaryService), section 8.5 (errors).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from domain.generation_schema import KanjiFacts


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


class DictionaryService:
    """Read-only gateway over the local dictionary index."""

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        if not self._db_path.exists():
            raise FileNotFoundError(
                f"Dictionary DB not found at {self._db_path}. "
                "Run: uv run python -m infrastructure.build_dictionary (from src/)"
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_kanji(self, kanji: str) -> KanjiFacts:
        """Exact lookup by kanji literal. Raises DictionaryMiss when absent."""
        with self._connect() as conn:
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

    def lookup_word(self, word: str, limit: int = 5) -> list[WordHit]:
        """Exact-match word lookup. Returns [] when absent (advisory, not fatal)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT word, kana, meaning FROM words WHERE word = ? LIMIT ?",
                (word, limit),
            ).fetchall()
        return [WordHit(word=r["word"], kana=r["kana"], meaning=r["meaning"]) for r in rows]
