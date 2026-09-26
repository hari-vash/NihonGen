import asyncio
import urllib.error
from types import SimpleNamespace

import pytest

from domain.generation_schema import AnkiResult, KanjiLesson
from graph.nodes import anki as anki_nodes
from infrastructure.anki import (
    AnkiClient,
    AnkiConnectionError,
    AnkiError,
    DuplicateNoteError,
    format_card_back,
    format_verified_words,
)


class StubClient(AnkiClient):
    def __init__(self, script, deck="Test_Deck1"):
        super().__init__("http://127.0.0.1:8765", deck)
        self.script = script
        self.calls = []

    def _post(self, action, params=None):
        self.calls.append((action, params))
        if action not in self.script:
            raise AssertionError(f"unexpected Anki call: {action}")
        result = self.script[action]
        if isinstance(result, Exception):
            raise result
        return result


def _lesson():
    return KanjiLesson.model_validate(
        {
            "usage_guidelines": {"onyomi_rule": "c", "kunyomi_rule": "a"},
            "words": [{"word": "水泳", "kana": "すいえい", "meaning": "swimming", "romaji": "suiei"}],
            "mnemonic": "stream (memory aid)",
            "dialogue": [],
        }
    )


def _facts():
    return SimpleNamespace(onyomi=["スイ"], kunyomi=["みず"], meanings=["water"], stroke_count=4)


def _runtime(client):
    return SimpleNamespace(context=SimpleNamespace(anki=client))


def _state(**over):
    state = {
        "kanji": "水",
        "dictionary_facts": _facts(),
        "lesson": _lesson(),
    }
    state.update(over)
    return state


def test_ping_ok():
    client = StubClient({"version": {"result": 6, "error": None}})
    assert asyncio.run(client.ping()) is True


def test_connection_error_is_typed():
    client = StubClient({"version": urllib.error.URLError("refused")})
    with pytest.raises(AnkiConnectionError):
        asyncio.run(client.ping())


def test_duplicate_maps_to_typed_error():
    client = StubClient({"addNote": {"error": "cannot create note because it is a duplicate"}})
    with pytest.raises(DuplicateNoteError):
        client._request_sync("addNote", {})


def test_plain_error_maps_to_anki_error():
    client = StubClient({"findNotes": {"error": "weird"}})
    with pytest.raises(AnkiError):
        client._request_sync("findNotes", {})


def test_find_notes_and_get_back():
    client = StubClient(
        {
            "findNotes": {"result": [11], "error": None},
            "notesInfo": {"result": [{"fields": {"Back": {"value": "OLD BACK"}}}], "error": None},
        }
    )
    assert asyncio.run(client.find_notes("水")) == [11]
    assert asyncio.run(client.get_back(11)) == "OLD BACK"


def test_get_back_uses_notes_action():
    client = StubClient(
        {
            "findNotes": {"result": [11], "error": None},
            "notesInfo": {"result": [{"fields": {"Back": {"value": "OLD BACK"}}}], "error": None},
        }
    )
    asyncio.run(anki_nodes.check_anki(_state(), _runtime(client)))
    actions = [c[0] for c in client.calls]
    assert actions == ["findNotes", "notesInfo"]
    assert client.calls[1][1] == {"notes": [11]}


def test_check_anki_stores_current_back():
    client = StubClient(
        {
            "findNotes": {"result": [11], "error": None},
            "notesInfo": {"result": [{"fields": {"Back": {"value": "OLD BACK"}}}], "error": None},
        }
    )
    out = asyncio.run(anki_nodes.check_anki(_state(), _runtime(client)))
    assert out == {"exists": True, "current_back": "OLD BACK"}


def test_check_anki_missing():
    client = StubClient({"findNotes": {"result": [], "error": None}})
    out = asyncio.run(anki_nodes.check_anki(_state(), _runtime(client)))
    assert out == {"exists": False, "current_back": None}


def test_create_flashcard_returns_result():
    client = StubClient(
        {
            "findNotes": {"result": [], "error": None},
            "addNote": {"result": 99, "error": None},
        }
    )
    out = asyncio.run(anki_nodes.create_flashcard(_state(), _runtime(client)))
    status = out["anki_status"]
    assert isinstance(status, AnkiResult)
    assert (status.ok, status.action) == (True, "created")
    back = client.calls[1][1]["note"]["fields"]["Back"]
    assert "水泳" in back and "suiei" in back


def test_create_duplicate_guard_precheck():
    client = StubClient({"findNotes": {"result": [11], "error": None}})
    out = asyncio.run(anki_nodes.create_flashcard(_state(), _runtime(client)))
    assert out["anki_status"].action == "exists"
    assert out["anki_status"].ok is False
    assert [c[0] for c in client.calls] == ["findNotes"]


def test_create_duplicate_error_caught():
    client = StubClient(
        {
            "findNotes": {"result": [], "error": None},
            "addNote": DuplicateNoteError("dup"),
        }
    )
    out = asyncio.run(anki_nodes.create_flashcard(_state(), _runtime(client)))
    assert out["anki_status"].action == "exists"


def test_update_flashcard_returns_result():
    client = StubClient(
        {
            "findNotes": {"result": [11], "error": None},
            "updateNoteFields": {"result": None, "error": None},
        }
    )
    out = asyncio.run(anki_nodes.update_flashcard(_state(), _runtime(client)))
    assert out["anki_status"].action == "updated"
    assert out["anki_status"].ok is True


def test_update_missing_note_reports_cleanly():
    client = StubClient({"findNotes": {"result": [], "error": None}})
    out = asyncio.run(anki_nodes.update_flashcard(_state(), _runtime(client)))
    assert out["anki_status"].ok is False


def test_approval_message_shows_diff():
    msg = anki_nodes.approval_message(
        _state(current_back="OLD<br>BACK"), "Test_Deck1"
    )
    assert "Current card:" in msg and "OLD\nBACK" in msg
    assert "Proposed card:" in msg and "水泳" in msg


def test_unclear_approval_notice():
    notice = anki_nodes.unclear_approval_notice(
        {"reply_intent": "unclear", "last_reply": "only the readings"}
    )
    assert notice is not None
    assert "only the readings" in notice and "yes or no" in notice


def test_unclear_approval_notice_absent_first_visit():
    assert anki_nodes.unclear_approval_notice({"reply_intent": "answer", "last_reply": "yes"}) is None
    assert anki_nodes.unclear_approval_notice({}) is None


def test_format_card_back_golden():
    back = format_card_back(_facts(), _lesson())
    assert "On'yomi: スイ" in back
    assert "- 水泳 [すいえい] (suiei) - swimming" in back
    assert "Memory Aid:" in back
    assert format_verified_words([]) == ""
