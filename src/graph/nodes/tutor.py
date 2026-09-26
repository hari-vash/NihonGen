"""Bounded tutor: answers free-form questions, then hands control back.

SPEC 6: agentic but bounded and read-only. Max 3 tool calls, no grading,
no advancing, no Anki. The answer is served through pending_explanation
and the graph returns to the prompt that asked (via reply_prompt).
A question never consumes a quiz round (FR-10).
"""

from __future__ import annotations

from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.runtime import Runtime
from langchain.tools import tool

from graph.context import RuntimeContext
from graph.helpers import message_to_text
from graph.state import State
from infrastructure.dictionary import DictionaryMiss

MAX_TUTOR_TOOL_CALLS = 3

TUTOR_SYSTEM = (
    "You are a friendly Japanese tutor answering one learner question. "
    "Use the provided dictionary tools when you are unsure about a reading, "
    "meaning, or word. Answer succinctly in at most 6 sentences. "
    "Learner commands you may mention when asked for help: skip (move to the "
    "next kanji), stop (end the session), help. "
    "Never grade the learner, never mention quizzes or flashcards."
)


def _make_tools(dictionary):
    @tool("lookup_kanji", description="Look up verified kanji facts (readings, meanings, strokes).")
    def lookup_kanji(kanji: str) -> str:
        try:
            facts = dictionary.get_kanji(kanji)
        except DictionaryMiss as exc:
            return str(exc)
        return facts.to_polished_string()

    @tool("lookup_word", description="Look up a Japanese word (kana reading and meaning).")
    def lookup_word(word: str) -> str:
        hits = dictionary.lookup_word(word)
        if not hits:
            return f"No dictionary entry for {word!r}."
        return "; ".join(f"{h.word} [{h.kana}] - {h.meaning}" for h in hits[:3])

    return {"lookup_kanji": lookup_kanji, "lookup_word": lookup_word}


async def tutor(state: State, runtime: Runtime[RuntimeContext]):
    dictionary = runtime.context.dictionary
    tools = _make_tools(dictionary)
    llm_with_tools = runtime.context.models.llm.bind_tools(list(tools.values()))

    facts = state.get("dictionary_facts")
    context = (
        f"Target kanji: {state.get('kanji')}\n"
        f"Verified facts:\n{facts.model_dump_json(indent=2) if facts else 'none'}"
    )
    messages: list = [
        SystemMessage(content=f"{TUTOR_SYSTEM}\n\n{context}"),
        HumanMessage(content=state.get("last_reply") or ""),
    ]

    calls = 0
    answer = ""
    evidence: list[str] = []
    for _ in range(MAX_TUTOR_TOOL_CALLS + 1):
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)
        pending = [c for c in (getattr(response, "tool_calls", None) or []) if calls < MAX_TUTOR_TOOL_CALLS]
        if not pending:
            answer = message_to_text(response) or answer
            break
        for call in pending:
            calls += 1
            name = call.get("name", "")
            args = call.get("args", {}) or {}
            try:
                result = tools[name].invoke(args)
            except KeyError:
                result = f"Unknown tool {name!r}."
            evidence.append(str(result))
            messages.append(ToolMessage(content=str(result), tool_call_id=call.get("id", "")))

    if not answer:
        if evidence:
            shown = "\n".join(evidence)[:600]
            answer = f"Here's what I found in the dictionary:\n{shown}"
        else:
            answer = "I could not find an answer. Let me know if you want me to explain that differently."

    return {"messages": [AIMessage(content=answer)], "pending_explanation": answer}
