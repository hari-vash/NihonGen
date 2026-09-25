from langgraph.graph import MessagesState
from typing_extensions import NotRequired

from domain.generation_schema import KanjiFacts, KanjiLesson, QuizAttempt, QuizQuestion

class State(MessagesState):
    # Input / document
    file_path: str
    deck: str

    # Document / MCP workflow state
    session_id: NotRequired[str]
    current_chunk: NotRequired[list[str]]
    current_index: NotRequired[int]
    has_more: NotRequired[bool]

    # Current Kanji
    kanji: NotRequired[str]
    dictionary_facts: NotRequired[KanjiFacts | None]
    lesson: NotRequired[KanjiLesson]
    verify_retries: NotRequired[int]
    verify_feedback: NotRequired[str | None]

    # Quiz
    current_question: NotRequired[QuizQuestion | None]
    quiz_attempts: NotRequired[list[QuizAttempt]]

    # Anki
    exists: NotRequired[bool]
    anki_status: NotRequired[str | None]

    # Human interaction
    last_reply: NotRequired[str | None]
    reply_prompt: NotRequired[str | None]
    reply_intent: NotRequired[str | None]
    pending_explanation: NotRequired[str | None]