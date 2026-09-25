"""Typed input path (FR-1, FR-2). No MCP involved."""

from graph.helpers import extract_kanji_ordered
from graph.state import State


def prepare_typed_input(state: State):
    kanjis = extract_kanji_ordered(state.get("typed_text") or "")
    if not kanjis:
        raise ValueError(
            "No kanji found in the typed text. Type a kanji, a word like 友達, "
            "or a short Japanese sentence."
        )

    return {
        "current_chunk": kanjis,
        "current_index": 0,
        "has_more": False,
    }
