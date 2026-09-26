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
from pydantic import BaseModel, Field

from domain.generation_schema import DialogueLine, KanjiLesson, VerifiedWord
from graph.context import RuntimeContext
from graph.state import State
from infrastructure.dictionary import WordHit
from infrastructure.romaji import kana_to_romaji, to_romaji

VERIFY_MAX_RETRIES = 2

MAX_GLOSSES_PER_WORD = 3

LOG_PATH = Path(__file__).resolve().parents[3] / "evals" / "verification_failures.jsonl"


class DialogueJudgment(BaseModel):
    """One judge verdict per dialogue line. Never stored in state."""

    flagged: bool = Field(description="True when the line must be dropped")
    reason: str = Field(default="", description="Short reason when flagged")


JUDGE_SYSTEM = (
    "You are a strict Japanese language judge. "
    "For the given dialogue line, flag it when the English translation "
    "does not match the Japanese meaning, or when the Japanese phrasing "
    "is unnatural (wrong particles, unnatural word choice, awkward use "
    "of the target kanji). Otherwise leave it unflagged."
)


def check_word(kanji: str, word: str, kana: str, hits: list[WordHit]) -> str | None:
    """Pure check. Returns a reason string, or None when the word is valid."""
    if not hits:
        return "not in JMdict"
    if kanji not in word:
        return f"does not contain {kanji}"
    if kana not in [h.kana for h in hits]:
        return f"reading {kana} not in JMdict ({', '.join(h.kana for h in hits)})"
    return None


def _short_meaning(meaning: str, limit: int = MAX_GLOSSES_PER_WORD) -> str:
    """Keep the first few JMdict glosses. Full gloss strings carry slang and
    clutter onto lessons and cards."""
    parts = [p.strip() for p in meaning.split(";")]
    return "; ".join(parts[:limit])


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


def _log_dialogue_flag(kanji: str, speaker: str, japanese: str, reason: str, retries: int) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kanji": kanji,
        "word": f"{speaker}: {japanese}",
        "kana": "",
        "reason": f"dialogue flagged: {reason}",
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


async def judge_dialogue_lines(lines: list[DialogueLine], kanji: str, llm) -> list[DialogueJudgment]:
    """One low-cost judge call per line. Skipped entirely on the retry path."""
    judge = llm.with_structured_output(DialogueJudgment, method="json_schema")
    judgments = []
    for line in lines:
        judgments.append(
            await judge.ainvoke(
                [
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"Target kanji: {kanji}\n"
                            f"Speaker: {line.speaker}\n"
                            f"Japanese: {line.japanese}\n"
                            f"English: {line.english}"
                        ),
                    },
                ]
            )
        )
    return judgments


def apply_judgments(
    lesson: KanjiLesson, judgments: list[DialogueJudgment]
) -> tuple[KanjiLesson, list[tuple[DialogueLine, str]]]:
    """Pure drop step. Returns (lesson with unflagged lines, flagged records)."""
    assert len(lesson.dialogue) == len(judgments), "judgments must align 1:1 with lines"
    kept: list[DialogueLine] = []
    flagged: list[tuple[DialogueLine, str]] = []
    for line, judgment in zip(lesson.dialogue, judgments):
        if judgment.flagged:
            flagged.append((line, judgment.reason))
        else:
            kept.append(line)
    return lesson.model_copy(update={"dialogue": kept}), flagged


async def verify_lesson(state: State, runtime: Runtime[RuntimeContext]):
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
                    meaning=_short_meaning(hits[0].meaning),
                    romaji=kana_to_romaji(w.kana),
                )
            )
        else:
            problems.append((w.word, w.kana, reason))

    if problems and retries < VERIFY_MAX_RETRIES:
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
    lesson = _fill_dialogue_romaji(lesson.model_copy(update={"words": valid}))

    judgments = await judge_dialogue_lines(
        lesson.dialogue, kanji, runtime.context.models.llm
    )
    lesson, flagged = apply_judgments(lesson, judgments)
    for line, reason in flagged:
        _log_dialogue_flag(kanji, line.speaker, line.japanese, reason, retries)

    return {
        "lesson": lesson,
        "verify_retries": 0,
        "verify_feedback": None,
    }
