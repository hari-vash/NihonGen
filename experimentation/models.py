"""Model bindings: one base client, one schema per binding."""

from dataclasses import dataclass

from langchain_google_genai import ChatGoogleGenerativeAI

from schemas import ApprovalDecision, KanjiLesson, TurnIntent

MODEL_NAME = "gemini-3.5-flash-lite"
ROUTER_MAX_TOKENS = 200


@dataclass(frozen=True, slots=True)
class Models:
    tutor: ChatGoogleGenerativeAI
    router_intent: object
    router_approval: object
    lesson: object


def build_models() -> Models:
    tutor = ChatGoogleGenerativeAI(model=MODEL_NAME)
    router = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0,
        max_output_tokens=ROUTER_MAX_TOKENS,
    )
    return Models(
        tutor=tutor,
        router_intent=router.with_structured_output(TurnIntent, method="json_schema"),
        router_approval=router.with_structured_output(ApprovalDecision, method="json_schema"),
        lesson=tutor.with_structured_output(KanjiLesson, method="json_schema"),
    )
