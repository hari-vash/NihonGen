"""Pure kanji extraction from arbitrary text."""

import re

_KANJI = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def extract_kanji(text: str) -> list[str]:
    """Unique kanji in first-appearance order."""
    return list(dict.fromkeys(_KANJI.findall(text)))
