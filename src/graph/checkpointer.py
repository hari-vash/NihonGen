from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from domain.generation_schema import KanjiFormat,KanjiLesson,QuizEvaluation


def create_checkpointer() -> MemorySaver:
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            KanjiFormat,
            KanjiLesson,
            QuizEvaluation,
        ]
    )

    return MemorySaver(serde=serde)