"""Graph state: what one lesson needs, and nothing else.

Every key is NotRequired so a turn can send only {"messages": [...]} and let the
checkpoint supply the rest. Facts and lessons stay as pydantic models; the
checkpointer allowlists them in main.py rather than here.
"""

from typing import Literal, NotRequired
from langgraph.graph import MessagesState
from schemas import KanjiFacts, KanjiLesson


class KanjiState(MessagesState):
    queue: NotRequired[list[str]]
    current_kanji: NotRequired[str | None]
    facts_by_kanji: NotRequired[dict[str, KanjiFacts]]
    lesson: NotRequired[KanjiLesson | None]
    taught: NotRequired[list[str]]
    verify_retries: NotRequired[int]
    verify_feedback: NotRequired[str | None]
    verdict: NotRequired[Literal["pass", "reject"]]
    awaiting_approval: NotRequired[bool]
    approve: NotRequired[bool]
    ask: NotRequired[bool]