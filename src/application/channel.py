"""I/O seam: the graph loop talks to a Channel, never to stdin/stdout.

CliChannel preserves the current terminal behavior (typewriter effect).
DiscordChannel arrives in Item 2. FakeChannel serves tests.
"""

from __future__ import annotations

import asyncio
import time
from typing import Protocol


class Channel(Protocol):
    async def send(self, text: str) -> None:
        """Deliver one message block to the learner."""
        ...

    async def ask(self, prompt: str) -> str:
        """Show a prompt and collect one reply."""
        ...


def typewriter_block(text: str, delay: float = 0.01) -> None:
    for char in str(text):
        print(char, end="", flush=True)
        time.sleep(delay)
    print()


class CliChannel:
    async def send(self, text: str) -> None:
        await asyncio.to_thread(typewriter_block, text)

    async def ask(self, prompt: str) -> str:
        return await asyncio.to_thread(input, prompt)


class FakeChannel:
    """Scripted channel for tests. Replies are consumed in order."""

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.sent: list[str] = []

    async def send(self, text: str) -> None:
        self.sent.append(text)

    async def ask(self, prompt: str) -> str:
        self.sent.append(prompt)
        if not self.replies:
            raise AssertionError("FakeChannel ran out of scripted replies")
        return self.replies.pop(0)
