from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from domain.generation_schema import KanjiFacts,KanjiLesson,QuizAttempt,QuizEvaluation,QuizQuestion


def create_checkpointer() -> MemorySaver:
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            KanjiFacts,
            KanjiLesson,
            QuizAttempt,
            QuizEvaluation,
            QuizQuestion,
        ]
    )

    return MemorySaver(serde=serde)