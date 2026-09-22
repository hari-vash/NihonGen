from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from domain.generation_schema import KanjiFacts,KanjiLesson,QuizEvaluation


def create_checkpointer() -> MemorySaver:
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            KanjiFacts,
            KanjiLesson,
            QuizEvaluation,
        ]
    )

    return MemorySaver(serde=serde)