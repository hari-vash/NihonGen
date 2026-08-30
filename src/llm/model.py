from dataclasses import dataclass
from langchain_google_genai import ChatGoogleGenerativeAI
from domain.generation_schema import KanjiFormat,KanjiLesson,QuizEvaluation

@dataclass(frozen=True, slots=True)
class LLMModels:
    llm: ChatGoogleGenerativeAI
    kanji: object
    lesson: object
    quiz_evaluation: object


def build_models() -> LLMModels:
    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

    return LLMModels(
        llm=llm,
        kanji=llm.with_structured_output(KanjiFormat,method="json_schema"),
        lesson=llm.with_structured_output(KanjiLesson,method="json_schema"),
        quiz_evaluation=llm.with_structured_output(QuizEvaluation,method="json_schema")
    )