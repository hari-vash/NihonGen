import asyncio
from types import SimpleNamespace

from domain.generation_schema import KanjiOutcome
from graph.nodes import anki as anki_nodes
from graph.nodes.kanji import advance_kanji, select_kanji


class FakeAnki:
    def __init__(self, notes):
        self.notes = notes

    async def find_notes(self, kanji):
        return list(self.notes)


def _runtime(notes):
    return SimpleNamespace(context=SimpleNamespace(anki=FakeAnki(notes)))


def _select_state(**over):
    state = {"current_chunk": ["水", "車"], "current_index": 0, "messages": []}
    state.update(over)
    return state


def test_select_early_check_hit_notices():
    out = asyncio.run(select_kanji(_select_state(), _runtime([7])))
    assert out["exists"] is True
    assert "already in your Anki deck" in out["pending_explanation"]


def test_select_early_check_miss_silent():
    out = asyncio.run(select_kanji(_select_state(), _runtime([])))
    assert out["exists"] is False
    assert out["pending_explanation"] is None


def test_select_preserves_results():
    prior = [KanjiOutcome(kanji="日", outcome="added")]
    out = asyncio.run(select_kanji(_select_state(), _runtime([])))
    assert "results" not in out
    assert prior[0].outcome == "added"


def test_advance_records_skip_decline_passed():
    assert advance_kanji(
        {"kanji": "水", "current_index": 0, "reply_intent": "skip_kanji"}
    )["results"][0].outcome == "skipped"
    assert advance_kanji(
        {"kanji": "水", "current_index": 0, "reply_intent": "decline"}
    )["results"][0].outcome == "declined"
    assert advance_kanji(
        {"kanji": "水", "current_index": 0, "reply_intent": "answer"}
    )["results"][0].outcome == "passed"


def test_advance_skips_recorded_kanji():
    prior = [KanjiOutcome(kanji="水", outcome="parked")]
    out = advance_kanji(
        {"kanji": "水", "current_index": 0, "reply_intent": "skip_kanji", "results": prior}
    )
    assert out["results"] == prior
    assert out["current_index"] == 1


def test_park_records_parked():
    from graph.nodes.quiz import park_kanji

    out = park_kanji({"kanji": "水"})
    assert out["results"] == [KanjiOutcome(kanji="水", outcome="parked")]


def test_create_records_added():
    async def find_notes(kanji):
        return []

    async def add_note(front, back):
        return 5

    rt = SimpleNamespace(context=SimpleNamespace(anki=SimpleNamespace(find_notes=find_notes, add_note=add_note)))
    state = {
        "kanji": "水",
        "dictionary_facts": SimpleNamespace(onyomi=["ス"], kunyomi=["み"], meanings=["w"], stroke_count=1),
        "lesson": SimpleNamespace(words=[], to_polished_string=lambda: "L"),
    }
    out = asyncio.run(anki_nodes.create_flashcard(state, rt))
    assert out["results"] == [KanjiOutcome(kanji="水", outcome="added")]


def test_summary_render(capsys):
    from application import renderer

    renderer.render_summary(
        [
            KanjiOutcome(kanji="水", outcome="added"),
            KanjiOutcome(kanji="車", outcome="parked"),
        ]
    )
    text = capsys.readouterr().out
    assert "1 added, 1 parked" in text
    assert "水 — added" in text and "車 — parked" in text


def test_summary_empty(capsys):
    from application import renderer

    renderer.render_summary([])
    assert "No kanji completed" in capsys.readouterr().out
