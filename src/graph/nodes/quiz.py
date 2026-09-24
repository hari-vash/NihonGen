from langchain.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from graph.context import RuntimeContext
from graph.helpers import message_to_text
from graph.state import State
from llm.system_prompts import quiz_evaluation_prompt,quiz_question_prompt

def quiz_readiness(state: State):
    decision = interrupt({"type": "quiz_readiness",
            "message": (f"Are you ready for a quiz testing your knowledge about the Kanji {state['kanji']}?")}
        )

    return {"user_decision": str(decision), "last_reply": str(decision), "reply_prompt": "quiz_readiness"}


async def explain_again(state: State,runtime: Runtime[RuntimeContext]):
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

    return {"messages": [response], "quiz_round": 0, "pending_explanation": message_to_text(response)}


async def generate_quiz_question(state: State,runtime: Runtime[RuntimeContext]):
    round_number = state.get("quiz_round", 0) + 1
    prompt = quiz_question_prompt(
        kanji=state["kanji"],
        lesson=state["lesson"].to_polished_string(),
        round_number=round_number,
    )

    response = await runtime.context.models.llm.ainvoke(prompt)

    return {"messages": [response],"quiz_round": round_number}


def wait_for_answer(state: State):
    question_message = state["messages"][-1]
    question = message_to_text(question_message)

    answer = interrupt({
            "type": "quiz_answer",
            "question": question,
            "kanji": state["kanji"],
    })

    return {"messages": [HumanMessage(content=str(answer))], "pending_explanation": None, "last_reply": str(answer), "reply_prompt": "quiz_answer"}


async def evaluate_quiz_answer(state: State,runtime: Runtime[RuntimeContext]):
    prompt = SystemMessage(content=quiz_evaluation_prompt(kanji=state["kanji"],lesson=state["lesson"].to_polished_string()))
    recent_quiz_messages = state["messages"][-2:]

    response = await runtime.context.models.quiz_evaluation.ainvoke([prompt,*recent_quiz_messages])

    return {"quiz_evaluation": response,"messages": [AIMessage(content=(f"Feedback: {response.feedback}\n\n Explanation: {response.explanation}"))]}