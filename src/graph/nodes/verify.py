"""Lesson verification: code checks the LLM's words, never trusts them.

SPEC 8.3: every proposed word must exist in JMdict, contain the target
kanji, and match a JMdict reading. Failures retry with feedback
(max VERIFY_MAX_RETRIES), then the word is dropped and logged.
Romaji is filled by code only for surviving words (SPEC FR-9).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from langgraph.runtime import Runtime

from domain.generation_schema import KanjiLesson, VerifiedWord
from graph.context import RuntimeContext
from graph.state import State
from infrastructure.dictionary import WordHit
from infrastructure.romaji import kana_to_romaji, to_romaji

VERIFY_MAX_RETRIES = 2

LOG_PATH = Path(__file__).resolve().parents[3] / "evals" / "verification_failures.jsonl"


def check_word(kanji: str, word: str, kana: str, hits: list[WordHit]) -> str | None:
    """Pure check. Returns a reason string, or None when the word is valid."""
    if not hits:
        return "not in JMdict"
    if kanji not in word:
        return f"does not contain {kanji}"
    if kana not in [h.kana for h in hits]:
        return f"reading {kana} not in JMdict ({', '.join(h.kana for h in hits)})"
    return None


def _log_failure(kanji: str, word: str, kana: str, reason: str, retries: int) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kanji": kanji,
        "word": word,
        "kana": kana,
        "reason": reason,
        "retries": retries,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _fill_dialogue_romaji(lesson: KanjiLesson) -> KanjiLesson:
    lines = [
        line.model_copy(update={"romaji": to_romaji(line.japanese)})
        for line in lesson.dialogue
    ]
    return lesson.model_copy(update={"dialogue": lines})


def verify_lesson(state: State, runtime: Runtime[RuntimeContext]):
    kanji = state["kanji"]
    lesson = state["lesson"]
    retries = state.get("verify_retries") or 0

    valid: list[VerifiedWord] = []
    problems: list[tuple[str, str, str]] = []  # (word, kana, reason)

    for w in lesson.words:
        hits = runtime.context.dictionary.lookup_word(w.word)
        reason = check_word(kanji, w.word, w.kana, hits)
        if reason is None:
            valid.append(
                VerifiedWord(
                    word=w.word,
                    kana=w.kana,
                    meaning=hits[0].meaning,
                    romaji=kana_to_romaji(w.kana),
                )
            )
        else:
            problems.append((w.word, w.kana, reason))

    if not problems:
        return {
            "lesson": _fill_dialogue_romaji(lesson.model_copy(update={"words": valid})),
            "verify_retries": 0,
            "verify_feedback": None,
        }

    if retries < VERIFY_MAX_RETRIES:
        detail = "; ".join(f"{word} [{kana}] rejected: {reason}" for word, kana, reason in problems)
        return {
            "verify_retries": retries + 1,
            "verify_feedback": (
                f"Previous attempt failed verification ({retries + 1}/{VERIFY_MAX_RETRIES}): {detail}. "
                "Replace rejected words with common JMdict words containing the kanji."
            ),
        }

    for word, kana, reason in problems:
        _log_failure(kanji, word, kana, reason, retries)
    return {
        "lesson": _fill_dialogue_romaji(lesson.model_copy(update={"words": valid})),
        "verify_retries": 0,
        "verify_feedback": None,
    }
