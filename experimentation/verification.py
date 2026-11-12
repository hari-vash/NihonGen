"""Word verification: code checks the LLM's words, never trusts them.

A word survives only if it exists in JMdict, contains the target kanji, and its
kana matches a JMdict reading. Survivors are rebuilt from dictionary data, so
meaning and romaji are never LLM-authored.
"""

from typing import Callable

from dictionary import WordHit
from romaji import kana_to_romaji
from schemas import DialogueLine, VerifiedWord

MAX_GLOSSES = 3


def check_word(kanji: str, word: str, kana: str, hits: list[WordHit]) -> str | None:
    """Return a rejection reason, or None when the word is valid."""
    if not hits:
        return "not in dictionary"
    if kanji not in word:
        return f"does not contain {kanji}"
    if kana not in {hit.kana for hit in hits}:
        return f"reading {kana} not in dictionary ({', '.join(h.kana for h in hits)})"
    return None


def short_meaning(meaning: str, limit: int = MAX_GLOSSES) -> str:
    """Keep the first few glosses. Full gloss strings carry slang and clutter."""
    parts = [p.strip() for p in meaning.split(";")]
    return "; ".join(parts[:limit])


def verify_words(
    words: list[VerifiedWord],
    kanji: str,
    lookup: Callable[[str], list[WordHit]],
) -> tuple[list[VerifiedWord], list[tuple[str, str, str]]]:
    """Return (verified words rebuilt from the dictionary, rejections)."""
    kept: list[VerifiedWord] = []
    rejected: list[tuple[str, str, str]] = []

    for candidate in words:
        hits = lookup(candidate.word)
        reason = check_word(kanji, candidate.word, candidate.kana, hits)
        if reason is not None:
            rejected.append((candidate.word, candidate.kana, reason))
            continue
        kept.append(
            VerifiedWord(
                word=candidate.word,
                kana=candidate.kana,
                meaning=short_meaning(hits[0].meaning),
                romaji=kana_to_romaji(candidate.kana),
            )
        )

    return list({w.word: w for w in kept}.values()), rejected


def dialogue_uses_verified_words(
    lines: list[DialogueLine], words: list[VerifiedWord]
) -> tuple[list[DialogueLine], list[DialogueLine]]:
    """Keep lines that use at least one verified word."""
    texts = [w.word for w in words]
    kept: list[DialogueLine] = []
    dropped: list[DialogueLine] = []
    for line in lines:
        if any(text and text in line.japanese for text in texts):
            kept.append(line)
        else:
            dropped.append(line)
    return kept, dropped
