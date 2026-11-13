"""Prompt builders. One function per prompt, so each is readable and testable."""

from schemas import KanjiFacts

APPROVAL_QUESTION = "Shall we move on to the next kanji?"

TUTOR_RULES = """You are a friendly Japanese kanji tutor working with one learner.

Rules:
- Answer the learner's question in at most 6 sentences.
- Use only the dictionary facts you are given. Never invent a reading, meaning,
  stroke count, or example word.
- If the learner asks about a kanji you have no facts for, say it is not in your
  dictionary data. Do not guess.
- Never quiz the learner and never mention flashcards.
"""

READING_NOTATION = """Reading notation in the facts above:
- a leading or trailing "-" marks an affix (e.g. みず- attaches to another word)
- a "." separates the stem from trailing hiragana (e.g. い.る is read いる)
Never copy "-" or "." into a word or a kana reading."""


def tutor_system(facts: KanjiFacts | None) -> str:
    if facts is None:
        return TUTOR_RULES + "\nNo kanji is active yet."
    return (
        f"{TUTOR_RULES}\n"
        f"Current kanji: {facts.kanji}\n"
        f"Verified facts:\n{facts.to_polished_string()}"
    )


def lesson_prompt(kanji: str, facts: KanjiFacts, feedback: str | None = None) -> str:
    prompt = (
        f"Write one short lesson for the kanji {kanji}.\n\n"
        f"Verified dictionary facts (authoritative, never contradict them):\n"
        f"{facts.to_polished_string()}\n\n"
        f"{READING_NOTATION}\n\n"
        "Rules:\n"
        f"1. words: 2-4 common example words in dictionary form. No conjugations\n"
        f"   (水泳, not 水泳した). Every word must contain {kanji}.\n"
        "   Use the kana exactly as written in the facts.\n"
        "2. mnemonic: one short memory aid. It is a memory aid, not a historical fact.\n"
        "3. dialogue: 2-4 short lines. Every line must contain one of the words from (1).\n"
        "4. Leave every romaji field blank."
    )
    if feedback:
        prompt += (
            f"\n\nYour previous attempt failed verification:\n{feedback}\n"
            "Fix exactly these problems."
        )
    return prompt


def idle_router_prompt(last_message: str, taught: list[str]) -> str:
    taught_text = ", ".join(taught) if taught else "none"
    return (
        "The learner has no kanji in progress.\n"
        f"Already taught this session: {taught_text}.\n\n"
        "Decide what the learner's message is asking for, using the TurnIntent schema.\n"
        "A message that merely mentions a kanji is not a sentence: "
        '"水って何？" is a question.\n'
        'Only use kind="teach_request" when the learner explicitly asks to be taught '
        "a kanji.\n\n"
        "Learner message:\n"
        f"{last_message}"
    )


def approval_router_prompt(last_message: str, last_question: str) -> str:
    return (
        f'You asked the learner: "{last_question}"\n'
        "Their reply:\n"
        f"{last_message}\n\n"
        "Decide using the ApprovalDecision schema:\n"
        "- approve: they consent to moving on to the next kanji.\n"
        '- ask: they want something explained; "Yes, but how is it read?" is both\n'
        "  approve and ask.\n"
        "- teach: they named a specific kanji they want taught next.\n"
        "Never infer approval from politeness, and never infer it from a question."
    )