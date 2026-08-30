from langgraph.graph import MessagesState
from typing_extensions import NotRequired

from domain.generation_schema import KanjiFormat, KanjiLesson, QuizEvaluation

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
    kanji_info: NotRequired[KanjiFormat]
    lesson: NotRequired[KanjiLesson]

    # Quiz
    quiz_round: NotRequired[int]
    quiz_evaluation: NotRequired[QuizEvaluation]

    # Anki
    exists: NotRequired[bool]
    anki_status: NotRequired[str]

    # Human interaction
    user_decision: NotRequired[str]