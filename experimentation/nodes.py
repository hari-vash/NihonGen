"""Nodes: one job each, (state) -> dict.

Deterministic nodes first (prepare, verify_lesson, notice, advance), then the
four that call a model (idle_router, draft_lesson, answer, approval_router).
Every model call is injected, so the gate runs with fakes and no network.
"""

from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage, convert_to_messages

from dictionary import DictionaryMiss, WordHit, lookup_kanji, lookup_word
from extraction import extract_kanji
from prompts import (
    APPROVAL_QUESTION,
    approval_router_prompt,
    idle_router_prompt,
    lesson_prompt,
    tutor_system,
)
from schemas import KanjiFacts, KanjiLesson
from state import KanjiState
from verification import dialogue_uses_verified_words, verify_words

MAX_VERIFY_RETRIES = 2
MIN_DIALOGUE_LINES = 2


def say(text: str) -> dict:
    """One assistant message. Never append to state["messages"] by hand."""
    return {"messages": [("assistant", text)]}


def message_text(message: Any) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "") if isinstance(block, dict) else str(block)
        for block in content
    )


def last_user_text(state: KanjiState) -> str:
    for message in reversed(convert_to_messages(state.get("messages") or [])):
        if message.type == "human":
            return message_text(message)
    return ""


def last_ai_text(state: KanjiState) -> str:
    for message in reversed(convert_to_messages(state.get("messages") or [])):
        if message.type == "ai":
            return message_text(message)
    return ""


def clean_kanji(name: str | None) -> str | None:
    """A learner-named kanji is usable only if it resolves to exactly one."""
    if not name:
        return None
    found = extract_kanji(name)
    return found[0] if len(found) == 1 else None


def _teachable(kanji: str, lookup: Callable[[str], KanjiFacts]) -> bool:
    try:
        lookup(kanji)
    except DictionaryMiss:
        return False
    return True


def format_rejections(rejected: list[tuple[str, str, str]]) -> str:
    return "; ".join(f"{word} ({kana}): {reason}" for word, kana, reason in rejected)


def render_lesson(lesson: KanjiLesson, facts: KanjiFacts) -> str:
    words = "\n".join(
        f"- {w.word} [{w.kana}] {w.romaji} - {w.meaning}" for w in lesson.words
    )
    dialogue = "\n".join(
        f"{line.speaker}: {line.japanese}\n  {line.english}" for line in lesson.dialogue
    )
    strokes = facts.stroke_count if facts.stroke_count is not None else "—"
    grade = facts.grade if facts.grade is not None else "—"
    return (
        f"# {facts.kanji}\n"
        f"On'yomi: {', '.join(facts.onyomi) or '—'} | "
        f"Kun'yomi: {', '.join(facts.kunyomi) or '—'}\n"
        f"Meaning: {', '.join(facts.meanings) or '—'} | "
        f"Strokes: {strokes} | Grade: {grade}\n\n"
        f"Words\n{words}\n\n"
        f"Memory aid\n{lesson.mnemonic}\n\n"
        f"Reading rules\n"
        f"- On'yomi: {lesson.usage_guidelines.onyomi_rule}\n"
        f"- Kun'yomi: {lesson.usage_guidelines.kunyomi_rule}\n\n"
        f"Dialogue\n{dialogue}"
    )


def prepare(
    state: KanjiState, lookup: Callable[[str], KanjiFacts] = lookup_kanji
) -> dict:
    """Start a lesson: take the front of the queue and load its facts."""
    queue = list(state.get("queue") or [])
    if not queue:
        return {
            "outcome": "miss",
            "current_kanji": None,
            "lesson": None,
            "verify_retries": 0,
            "verify_feedback": None,
        }

    kanji, rest = queue[0], queue[1:]
    try:
        facts = lookup(kanji)
    except DictionaryMiss:
        return {
            "queue": rest,
            "outcome": "miss",
            "current_kanji": kanji,
            "lesson": None,
            "verify_retries": 0,
            "verify_feedback": None,
        }

    return {
        "current_kanji": kanji,
        "facts_by_kanji": {**(state.get("facts_by_kanji") or {}), kanji: facts},
        "outcome": "pending",
        "lesson": None,
        "verify_retries": 0,
        "verify_feedback": None,
    }


def verify_lesson(
    state: KanjiState, lookup: Callable[[str], list[WordHit]] = lookup_word
) -> dict:
    """Gate the draft, then commit it or ask for a retry."""
    lesson = state.get("lesson")
    kanji = state.get("current_kanji")
    retries = state.get("verify_retries") or 0

    if lesson is None or kanji is None:
        return {
            "outcome": "reject",
            "verify_retries": retries + 1,
            "verify_feedback": "no lesson was drafted",
        }

    words, rejected = verify_words(lesson.words, kanji, lookup)
    lines, _dropped = dialogue_uses_verified_words(lesson.dialogue, words)

    problems: list[str] = []
    if not words:
        problems.append(
            f"no example word passed verification: {format_rejections(rejected)}"
        )
    if len(lines) < MIN_DIALOGUE_LINES:
        problems.append(
            f"only {len(lines)} of {len(lesson.dialogue)} dialogue lines used a "
            f"verified word; at least {MIN_DIALOGUE_LINES} must"
        )
    if problems:
        return {
            "outcome": "reject",
            "verify_retries": retries + 1,
            "verify_feedback": "\n".join(problems),
        }

    verified = lesson.model_copy(update={"words": words, "dialogue": lines})
    return {
        "outcome": "pass",
        "lesson": verified,
        "messages": [
            (
                "assistant",
                render_lesson(verified, state["facts_by_kanji"][kanji])
                + "\n\n"
                + APPROVAL_QUESTION,
            )
        ],
        "awaiting_approval": True,
        "taught": [*(state.get("taught") or []), kanji],
        "verify_retries": retries,
        "verify_feedback": None,
    }


def notice(state: KanjiState) -> dict:
    """Every dead end gets words, never silence and never a repeat."""
    outcome = state.get("outcome")
    kanji = state.get("current_kanji")
    queue = list(state.get("queue") or [])

    if outcome == "miss" and kanji:
        return say(
            f"I can't teach {kanji}: it isn't in my dictionary data, and I won't "
            "invent readings or meanings. Send another sentence."
        )
    if outcome == "reject":
        return {
            **say(
                f"I couldn't build a lesson for {kanji} that passed verification "
                f"after {MAX_VERIFY_RETRIES + 1} attempts. The facts are fine; the "
                "example words or dialogue kept failing. Try a different kanji."
            ),
            "queue": queue[1:] if queue else [],
        }
    if state.get("taught"):
        return say(
            "That's everything from your text for now. Send more Japanese, or "
            "ask me about what we covered."
        )
    return say("Send me a sentence that contains kanji, or name one you want to learn.")


def advance(state: KanjiState) -> dict:
    """The learner approved: drop this kanji and forget the conversation about it."""
    queue = list(state.get("queue") or [])
    return {
        "queue": queue[1:] if queue else [],
        "current_kanji": None,
        "lesson": None,
        "approve": False,
        "ask": False,
        "awaiting_approval": False,
    }


def idle_router(
    state: KanjiState,
    model: Any,
    lookup: Callable[[str], KanjiFacts] = lookup_kanji,
) -> dict:
    """Classify the message and apply it: queue kanji, or leave the queue alone."""
    text = last_user_text(state)
    try:
        intent = model.invoke(idle_router_prompt(text, list(state.get("taught") or [])))
    except Exception:
        return {"intent": "question"}

    if intent.kind == "question":
        return {"intent": "question"}

    queue = list(state.get("queue") or [])

    if intent.kind == "teach_request":
        kanji = clean_kanji(intent.teach)
        if kanji is None or queue[:1] == [kanji]:
            return {"intent": "teach_request"}
        return {"intent": "teach_request", "queue": [kanji, *queue]}

    fresh = [
        kanji
        for kanji in extract_kanji(text)
        if kanji not in queue and _teachable(kanji, lookup)
    ]
    return {"intent": "sentence", "queue": [*queue, *fresh]}


def draft_lesson(state: KanjiState, model: Any) -> dict:
    """Produce one candidate lesson from the facts and the last rejection."""
    kanji = state.get("current_kanji")
    facts = (state.get("facts_by_kanji") or {}).get(kanji)
    if facts is None:
        return {"outcome": "miss"}

    prompt = lesson_prompt(kanji, facts, state.get("verify_feedback"))
    return {"lesson": model.invoke(prompt)}


def answer(state: KanjiState, model: Any) -> dict:
    """Answer the learner, and re-ask the approval question only if we stay put."""
    facts_by_kanji = state.get("facts_by_kanji") or {}
    kanji = state.get("current_kanji") or (state.get("taught") or [None])[-1]
    facts = facts_by_kanji.get(kanji) if kanji else None

    reply = model.invoke(
        [
            SystemMessage(content=tutor_system(facts)),
            HumanMessage(content=last_user_text(state)),
        ]
    )
    text = message_text(reply).rstrip()

    if state.get("awaiting_approval") and not state.get("approve"):
        text = f"{text}\n\n{APPROVAL_QUESTION}"

    return say(text)


def approval_router(state: KanjiState, model: Any) -> dict:
    """Classify the reply to the approval question. Never advances on doubt."""
    anchor = last_ai_text(state)
    if APPROVAL_QUESTION not in anchor:
        return {"approve": False, "ask": True}

    try:
        decision = model.invoke(
            approval_router_prompt(last_user_text(state), APPROVAL_QUESTION)
        )
    except Exception:
        return {"approve": False, "ask": True}

    queue = list(state.get("queue") or [])
    named = clean_kanji(decision.teach)
    if named and queue[:1] != [named]:
        queue = [named, *queue]

    return {"approve": decision.approve, "ask": decision.ask, "queue": queue}
