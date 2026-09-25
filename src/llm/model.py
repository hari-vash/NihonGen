from dataclasses import dataclass
from langchain_google_genai import ChatGoogleGenerativeAI
from domain.generation_schema import KanjiLesson,QuizEvaluation,QuizQuestion,ReplyIntent

@dataclass(frozen=True, slots=True)
class LLMModels:
    llm: ChatGoogleGenerativeAI
    lesson: object
    quiz_evaluation: object
    examiner: object
    classifier: object


def build_models() -> LLMModels:
    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

    return LLMModels(
        llm=llm,
        lesson=llm.with_structured_output(KanjiLesson,method="json_schema"),
        quiz_evaluation=llm.with_structured_output(QuizEvaluation,method="json_schema"),
        examiner=llm.with_structured_output(QuizQuestion,method="json_schema"),
        classifier=llm.with_structured_output(ReplyIntent,method="json_schema")
    )