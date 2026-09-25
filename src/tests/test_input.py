import pytest

from graph.helpers import extract_kanji_ordered
from graph.nodes.input import prepare_typed_input
from graph.routing import route_input


@pytest.mark.parametrize(
    "text,expected",
    [
        ("水", ["水"]),
        ("友達", ["友", "達"]),
        ("今日は水を飲みます。水が好きです。", ["今", "日", "水", "飲", "好"]),
        ("くるま", []),
        ("hello", []),
        ("", []),
    ],
)
def test_extract_kanji_ordered(text, expected):
    assert extract_kanji_ordered(text) == expected


def test_route_input():
    assert route_input({"input_mode": "typed"}) == "typed_input"
    assert route_input({"input_mode": "document"}) == "initialize_document"
    assert route_input({}) == "finish"
    assert route_input({"input_mode": "carrier pigeon"}) == "finish"


def test_prepare_typed_input_word():
    out = prepare_typed_input({"typed_text": "友達"})
    assert out == {"current_chunk": ["友", "達"], "current_index": 0, "has_more": False}


def test_prepare_typed_input_empty_raises():
    with pytest.raises(ValueError, match="No kanji found"):
        prepare_typed_input({"typed_text": "just kana くるま"})
    with pytest.raises(ValueError, match="No kanji found"):
        prepare_typed_input({})
