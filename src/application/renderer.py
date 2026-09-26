"""Pure string rendering. No printing, no input — the Channel delivers text."""

from domain.generation_schema import KanjiFacts, KanjiLesson, QuizAttempt, AnkiResult


def render_kanji(kanji: str) -> str:
    return "\n" + "=" * 60 + f"\nKANJI: {kanji}\n" + "-" * 60


def render_kanji_info(facts: KanjiFacts) -> str:
    return (
        "Kanji Information\n"
        + "-" * 60 + "\n"
        + facts.to_polished_string() + "\n"
        + "-" * 60
    )


def render_kanji_lesson(kanji_lesson: KanjiLesson) -> str:
    return (
        "Lesson\n"
        + "-" * 60 + "\n"
        + kanji_lesson.to_polished_string()
        + "=" * 60
    )


def render_quiz_result(attempt: QuizAttempt) -> str:
    text = "=" * 60 + "\nFeedback:\n" + attempt.feedback
    if attempt.outcome != "correct":
        text += "\n" + "-" * 60 + f"\nCorrect answer: {attempt.question.expected}"
    return text


def render_anki_result(anki_result: AnkiResult) -> str:
    mark = "✓" if anki_result.ok else "✗"
    return (
        "=" * 60 + "\n"
        + f"ANKI [{anki_result.action}]: {mark}\n"
        + anki_result.message + "\n"
        + "=" * 60
    )


def render_summary(results: list) -> str:
    text = "\n" + "=" * 60 + "\nSession summary:"
    if not results:
        text += "\nNo kanji completed this session."
    else:
        counts: dict = {}
        for outcome in results:
            counts[outcome.outcome] = counts.get(outcome.outcome, 0) + 1
        text += "\n" + ", ".join(f"{count} {name}" for name, count in sorted(counts.items()))
        for outcome in results:
            text += f"\n  {outcome.kanji} — {outcome.outcome}"
    return text + "\n" + "=" * 60


def render_additional_explanation(explanation: str) -> str:
    return (
        "=" * 60 + "\n"
        + "Additional Explanation:\n"
        + explanation + "\n"
        + "=" * 60
    )


def render_interrupt(interrupt_value: dict) -> str:
    text = "\n" + "=" * 60
    if isinstance(interrupt_value, dict):
        message = interrupt_value.get("message")
        if message:
            text += "\n" + message
        question = interrupt_value.get("question")
        if question:
            text += "\n" + question
    return text + "\n" + "=" * 60
