from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from domain.generation_schema import AnkiResult,KanjiFacts,KanjiLesson,QuizAttempt,QuizQuestion


def create_checkpointer() -> MemorySaver:
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            AnkiResult,
            KanjiFacts,
            KanjiLesson,
            QuizAttempt,
            QuizQuestion,
        ]
    )

    return MemorySaver(serde=serde)