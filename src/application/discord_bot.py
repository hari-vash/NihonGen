"""Discord adapter (Day 7). One thread per study session, owner-only.

SPEC 9: thread hosts the session (thread_id discord:<thread.id>), one
asyncio.Lock per thread, >2000-char chunking, attachments saved to temp
paths for the document flow, friendly errors posted to the thread.
The bot process owns a single MCP ClientSession for its lifetime.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import uuid
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from application.channel import Channel
from application.config import Config
from graph.builder import build_graph
from infrastructure.anki import AnkiClient, AnkiError
from infrastructure.dictionary import DictionaryService
from graph.context import RuntimeContext
from llm.model import build_models

CHUNK_LIMIT = 2000


def split_message(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
    """Split on newline boundaries, hard-chopping over-long lines. Pure."""
    if len(text) <= limit:
        return [text]
    lines: list[str] = []
    for line in text.split("\n"):
        while len(line) > limit:
            lines.append(line[:limit])
            line = line[limit:]
        lines.append(line)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        extra = len(line) + (1 if current else 0)
        if current and current_len + extra > limit:
            chunks.append("\n".join(current))
            current, current_len = [], 0
            extra = len(line)
        current.append(line)
        current_len += extra
    if current:
        chunks.append("\n".join(current))
    return chunks


def is_owner(author_id: int, owner_id: int) -> bool:
    return bool(owner_id) and author_id == owner_id


def build_initial_state(text: str | None, attachment_path: str | None) -> dict:
    if attachment_path:
        return {"input_mode": "document", "file_path": attachment_path}
    if text and text.strip():
        return {"input_mode": "typed", "typed_text": text.strip()}
    raise ValueError("Give me text or attach a TXT/PDF: /learn text:友達")


class DiscordChannel(Channel):
    def __init__(self, bot: commands.Bot, thread: discord.Thread, owner_id: int):
        self.bot = bot
        self.thread = thread
        self.owner_id = owner_id

    async def send(self, text: str) -> None:
        for chunk in split_message(text):
            await self.thread.send(chunk)

    async def ask(self, prompt: str) -> str:
        await self.send(prompt)

        def check(message: discord.Message) -> bool:
            return (
                message.channel.id == self.thread.id
                and not message.author.bot
                and is_owner(message.author.id, self.owner_id)
            )

        reply = await self.bot.wait_for("message", check=check)
        return reply.content.strip()


async def run_session(
    graph, initial_state: dict, thread_id: str, context: RuntimeContext,
    channel: DiscordChannel,
):
    from application.runner import run_interactive_graph

    config = {"configurable": {"thread_id": thread_id}}
    try:
        await run_interactive_graph(graph, initial_state, config, context, channel)
    except (AnkiError, RuntimeError, ValueError) as exc:
        await channel.send(f"\nStopped: {exc}")
    except Exception as exc:
        await channel.send(f"\nSomething went wrong ({type(exc).__name__}): {exc}")


def create_bot(app_config: Config, shared: dict) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    locks: dict[int, asyncio.Lock] = {}

    @bot.event
    async def on_ready():
        try:
            await bot.tree.sync()
        except discord.DiscordException:
            pass

    @bot.tree.command(name="learn", description="Start a kanji study session in a thread.")
    async def learn(
        interaction: discord.Interaction,
        text: str | None = None,
        attachment: discord.Attachment | None = None,
    ):
        if not is_owner(interaction.user.id, app_config.discord_owner_id):
            await interaction.response.send_message("This bot is owner-only.", ephemeral=True)
            return
        if app_config.discord_channel_id and interaction.channel_id != app_config.discord_channel_id:
            await interaction.response.send_message("Use /learn in the study channel.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        attachment_path = None
        if attachment is not None:
            suffix = Path(attachment.filename).suffix or ".txt"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.close()
            await attachment.save(tmp.name)
            attachment_path = tmp.name

        try:
            initial_state = build_initial_state(text, attachment_path)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        thread = await interaction.channel.create_thread(
            name=f"kanji-{uuid.uuid4().hex[:8]}",
            type=discord.ChannelType.public_thread,
        )
        await interaction.followup.send(f"Session started: {thread.mention}", ephemeral=True)

        lock = locks.setdefault(thread.id, asyncio.Lock())
        channel = DiscordChannel(bot, thread, app_config.discord_owner_id)

        async def _session():
            async with lock:
                await run_session(
                    shared["graph"], initial_state,
                    f"discord:{thread.id}", shared["context"], channel,
                )

        asyncio.create_task(_session())

    bot.locks = locks  # type: ignore[attr-defined]
    return bot


async def amain() -> None:
    load_dotenv()
    app_config = Config()
    if not app_config.discord_token or not app_config.discord_owner_id:
        print("Set DISCORD_TOKEN and DISCORD_OWNER_ID in .env to run the bot.")
        return

    src_dir = Path(__file__).resolve().parents[1]
    dict_path = Path(app_config.dict_path)
    if not dict_path.is_absolute():
        dict_path = src_dir.parent / dict_path

    graph = build_graph()
    shared = {
        "graph": graph,
        "models": build_models(),
        "dictionary": DictionaryService(dict_path),
        "anki": AnkiClient(app_config.anki_url, app_config.anki_deck),
        "config": app_config,
    }

    server_params = StdioServerParameters(
        command=sys.executable, args=[str(src_dir / "mcp_server.py")]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            shared["context"] = RuntimeContext(
                mcp_session=session,
                models=shared["models"],
                dictionary=shared["dictionary"],
                anki=shared["anki"],
                config=app_config,
            )
            bot = create_bot(app_config, shared)
            await bot.start(app_config.discord_token)


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
