from langchain.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from domain.generation_schema import KanjiOutcome, QuizAttempt, QuizGrade, QuizQuestion
from graph.context import RuntimeContext
from graph.helpers import message_to_text
from graph.state import State
from llm.system_prompts import quiz_grade_prompt,quiz_question_prompt

READING_FAMILY = {"reading", "onkun_choice", "in_context_reading", "word_reading"}
MEANING_FAMILY = {"meaning", "word_meaning"}

ALL_QUESTION_TYPES = sorted(READING_FAMILY | MEANING_FAMILY)

QUIZ_LENGTH = 5
QUIZ_MAX_MISSES = 2
MAX_REVIEW_CYCLES = 2


def mastery_gate(attempts: list[QuizAttempt]) -> str:
    """Pure pass rule (SPEC 8.1). Coverage is enforced at generation
    (allowed_types); this gate assumes well-formed input and owns
    count + misses only. dont_know counts as a miss."""
    misses = sum(1 for a in attempts if a.outcome != "correct")

    if misses > QUIZ_MAX_MISSES:
        return "fail"

    if len(attempts) >= QUIZ_LENGTH:
        return "pass"

    return "continue"


def allowed_types(attempts: list[QuizAttempt]) -> list[str]:
    """Pure coverage rule: by question 5 both families must appear. On the
    last question, restrict the examiner to the missing family."""
    used = {a.question.type for a in attempts}
    if len(attempts) >= QUIZ_LENGTH - 1:
        missing = []
        if not used & READING_FAMILY:
            missing.extend(sorted(READING_FAMILY))
        if not used & MEANING_FAMILY:
            missing.extend(sorted(MEANING_FAMILY))
        if missing:
            return missing
    return ALL_QUESTION_TYPES

def quiz_readiness(state: State):
    decision = interrupt({"type": "quiz_readiness",
            "message": (f"Are you ready for a quiz testing your knowledge about the Kanji {state['kanji']}?")}
        )

    return {"last_reply": str(decision), "reply_prompt": "quiz_readiness"}


async def explain_again(state: State,runtime: Runtime[RuntimeContext]):
    attempts = state.get("quiz_attempts") or []
    missed = [
        f"Q: {a.question.prompt}\nYou answered: {a.user_answer}\nCorrect: {a.question.expected}"
        for a in attempts
        if a.outcome != "correct"
    ]
    missed_section = (
        "\n\nThe learner missed these questions:\n" + "\n".join(missed)
        if missed else ""
    )
    response = await runtime.context.models.llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are a patient Japanese teacher. "
                    "Re-explain the target Kanji using the already "
                    "generated Kanji information and lesson below. "
                    "Do not contradict the existing information. "
                    "Make the explanation simpler and clearer. "
                    "Focus on likely learner confusion."
                    f"{missed_section}"
                )
            ),
            HumanMessage(
                content=(
                    f"Kanji: {state['kanji']}\n\n"
                    f"Kanji information:\n"
                    f"{state['dictionary_facts'].model_dump_json(indent=2)}\n\n"
                    f"Lesson:\n"
                    f"{state['lesson'].model_dump_json(indent=2)}"
                )
            )
        ]
    )

    cycles = state.get("review_cycles") or 0
    return {
        "messages": [response],
        "quiz_attempts": [],
        "current_question": None,
        "review_cycles": cycles + 1 if attempts else cycles,
        "pending_explanation": message_to_text(response),
    }


def park_kanji(state: State):
    """No Anki action. The kanji is parked after exhausting review cycles."""
    results = list(state.get("results") or [])
    kanji = state.get("kanji")
    if kanji and not any(r.kanji == kanji for r in results):
        results.append(KanjiOutcome(kanji=kanji, outcome="parked"))
    return {
        "results": results,
        "pending_explanation": (
            f"Parked {kanji}: two review cycles used without passing. "
            "Moving on for now — it will come back in a later session."
        )
    }


async def generate_quiz_question(state: State,runtime: Runtime[RuntimeContext]):
    attempts = state.get("quiz_attempts") or []
    round_number = len(attempts) + 1
    allowed = allowed_types(attempts)
    prompt = quiz_question_prompt(
        kanji=state["kanji"],
        lesson=state["lesson"].to_polished_string(),
        round_number=round_number,
        allowed=allowed,
    )

    question = await runtime.context.models.examiner.ainvoke(prompt)
    if question.type not in allowed:
        # One retry with a sterner instruction. Persistent defiance is
        # accepted as-is (still Literal-valid): coverage stays best-effort
        # rather than mislabelled.
        question = await runtime.context.models.examiner.ainvoke(
            prompt + "\n\nYour last question used a disallowed type. "
            f"Retry with a type from exactly: {', '.join(allowed)}."
        )

    return {
        "messages": [AIMessage(content=question.prompt)],
        "current_question": question,
    }


def current_question(state: State) -> str:
    """The question to (re-)ask. Stored question wins so a tutor detour never
    turns the tutor's answer into the question (T6)."""
    pending = state.get("current_question")
    if pending is not None:
        return pending.prompt
    return message_to_text(state["messages"][-1])


def wait_for_answer(state: State):
    question = current_question(state)

    answer = interrupt({
            "type": "quiz_answer",
            "question": question,
            "kanji": state["kanji"],
    })

    return {"messages": [HumanMessage(content=str(answer))], "pending_explanation": None, "last_reply": str(answer), "reply_prompt": "quiz_answer"}


async def evaluate_quiz_answer(state: State,runtime: Runtime[RuntimeContext]):
    question = state["current_question"]
    answer = state.get("last_reply") or ""
    attempts = state.get("quiz_attempts") or []

    if state.get("reply_intent") == "dont_know":
        grade = QuizGrade(
            outcome="miss",
            feedback=f"No problem — the answer is: {question.expected}.",
        )
    else:
        grader = runtime.context.models.llm.with_structured_output(QuizGrade, method="json_schema")
        grade = await grader.ainvoke(
            quiz_grade_prompt(
                kanji=state["kanji"],
                question=question.prompt,
                expected=question.expected,
                answer=answer,
            )
        )

    attempt = QuizAttempt(
        question=question,
        user_answer=answer,
        outcome="dont_know" if state.get("reply_intent") == "dont_know" else grade.outcome,
        feedback=grade.feedback,
    )

    return {
        "quiz_attempts": [*attempts, attempt],
        "current_question": None,
        "messages": [AIMessage(content=f"Feedback: {attempt.feedback}")],
    }