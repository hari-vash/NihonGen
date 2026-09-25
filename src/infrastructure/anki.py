"""AnkiConnect gateway. All Anki I/O goes through AnkiClient.

Transport only: card text builders are byte-identical ports of the old
tools.py formats. Item 2 unifies them into format_card_back().
SPEC 8.4, 8.5: blocking HTTP runs off the event loop; infrastructure
failure raises typed errors, never success strings.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from domain.generation_schema import KanjiFacts, KanjiLesson, VerifiedWord


class AnkiError(Exception):
    """Any Anki infrastructure failure. Never treated as success."""


class AnkiConnectionError(AnkiError):
    """AnkiConnect unreachable. Usually Anki is closed."""


class DuplicateNoteError(AnkiError):
    """AnkiConnect refused a create: the note already exists."""


def format_verified_words(words: list[VerifiedWord]) -> str:
    """Pure render of verified words for card backs. Offline-testable."""
    return "\n".join(f"- {w}" for w in words)


def format_card_back(facts: KanjiFacts, lesson: KanjiLesson) -> str:
    """Single card format for create and update (SPEC 8.4)."""
    readings = (
        f"On'yomi: {', '.join(facts.onyomi) or '—'}\n"
        f"Kun'yomi: {', '.join(facts.kunyomi) or '—'}\n"
        f"Meanings: {', '.join(facts.meanings) or '—'}\n"
        f"Strokes: {facts.stroke_count if facts.stroke_count is not None else '—'}"
    )
    words_str = format_verified_words(lesson.words) or "-"
    back = (
        f"{readings}\n\n"
        f"Example Words (verified):\n{words_str}\n\n"
        f"────────────────────\n\n"
        f"{lesson.to_polished_string()}"
    )
    return back.replace("\n", "<br>")


def parse_envelope(action: str, data: dict):
    """Map an AnkiConnect envelope to a result. Raises typed errors."""
    if data.get("error"):
        error = str(data["error"])
        if "duplicate" in error.lower():
            raise DuplicateNoteError(f"AnkiConnect Error: {error}")
        raise AnkiError(f"AnkiConnect Error: {error}")
    return data.get("result")


@dataclass
class AnkiClient:
    """Config-driven AnkiConnect client. Deck-scoped queries."""

    base_url: str
    deck: str = field(default="Test_Deck1")

    def _post(self, action: str, params: dict | None = None) -> dict:
        payload = {"action": action, "version": 6, "params": params or {}}
        request = urllib.request.Request(
            url=self.base_url,
            data=json.dumps(payload).encode("utf-8"),
        )
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())

    def _request_sync(self, action: str, params: dict | None = None):
        try:
            envelope = self._post(action, params)
        except urllib.error.URLError as exc:
            raise AnkiConnectionError(
                "Failed to connect! Is Anki open and running on your computer?"
            ) from exc
        return parse_envelope(action, envelope)

    async def _request(self, action: str, params: dict | None = None):
        return await asyncio.to_thread(self._request_sync, action, params)

    async def ping(self) -> bool:
        """True when AnkiConnect answers. Raises AnkiConnectionError otherwise."""
        await self._request("version")
        return True

    async def find_notes(self, kanji: str) -> list[int]:
        result = await self._request(
            "findNotes", {"query": f'deck:"{self.deck}" Front:"{kanji}"'}
        )
        return list(result or [])

    async def get_back(self, note_id: int) -> str:
        infos = await self._request("cardsInfo", {"notes": [note_id]})
        if not infos:
            raise AnkiError(f"No card info for note {note_id}.")
        return infos[0]["fields"]["Back"]["value"]

    async def add_note(self, front: str, back: str) -> int:
        return await self._request(
            "addNote",
            {
                "note": {
                    "deckName": self.deck,
                    "modelName": "Basic",
                    "fields": {"Front": front, "Back": back},
                }
            },
        )

    async def update_note(self, note_id: int, front: str, back: str) -> None:
        await self._request(
            "updateNoteFields",
            {"note": {"id": note_id, "fields": {"Front": front, "Back": back}}},
        )
