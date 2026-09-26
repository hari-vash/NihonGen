import asyncio
from types import SimpleNamespace

import pytest

from application.discord_bot import (
    DiscordChannel,
    build_initial_state,
    is_owner,
    split_message,
)


def test_split_message_short_untouched():
    assert split_message("hello") == ["hello"]
    assert split_message("x" * 2000) == ["x" * 2000]


def test_split_message_prefers_newlines():
    text = "a" * 1990 + "\n" + "b" * 100
    chunks = split_message(text)
    assert len(chunks) == 2
    assert all(len(c) <= 2000 for c in chunks)
    assert chunks[0] == "a" * 1990 and chunks[1] == "b" * 100


def test_split_message_long_line_splits():
    chunks = split_message("y" * 4500)
    assert len(chunks) == 3
    assert all(len(c) <= 2000 for c in chunks)
    assert "".join(chunks) == "y" * 4500


def test_is_owner():
    assert is_owner(123, 123) is True
    assert is_owner(456, 123) is False
    assert is_owner(123, 0) is False


def test_build_initial_state_typed():
    assert build_initial_state("友達", None) == {"input_mode": "typed", "typed_text": "友達"}


def test_build_initial_state_attachment_wins():
    out = build_initial_state("ignored", "/tmp/x.txt")
    assert out == {"input_mode": "document", "file_path": "/tmp/x.txt"}


def test_build_initial_state_empty_raises():
    with pytest.raises(ValueError, match="/learn"):
        build_initial_state(None, None)
    with pytest.raises(ValueError, match="/learn"):
        build_initial_state("   ", None)


class FakeThread:
    def __init__(self):
        self.id = 99
        self.sent = []

    async def send(self, text):
        self.sent.append(text)


class FakeAuthor:
    def __init__(self, author_id, bot=False):
        self.id = author_id
        self.bot = bot


class FakeMessage:
    def __init__(self, content, author_id, channel_id, bot=False):
        self.content = content
        self.author = FakeAuthor(author_id, bot)
        self.channel = SimpleNamespace(id=channel_id)


class FakeBot:
    def __init__(self, messages):
        self.messages = list(messages)

    async def wait_for(self, event, check=None):
        for message in self.messages:
            if check is None or check(message):
                return message
        raise AssertionError("no matching message (non-owner correctly skipped)")


def test_discord_channel_chunks_on_send():
    thread = FakeThread()
    channel = DiscordChannel(FakeBot([]), thread, owner_id=1)
    asyncio.run(channel.send("a" * 1990 + "\n" + "b" * 100))
    assert len(thread.sent) == 2


def test_discord_channel_ask_ignores_non_owner():
    thread = FakeThread()
    stranger = FakeMessage("do evil", author_id=666, channel_id=99)
    owner = FakeMessage("yes", author_id=1, channel_id=99)
    channel = DiscordChannel(FakeBot([stranger, owner]), thread, owner_id=1)
    assert asyncio.run(channel.ask("ready?")) == "yes"
    assert thread.sent == ["ready?"]
