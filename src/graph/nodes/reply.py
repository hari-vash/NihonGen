"""Reply classification: deterministic pre-pass first, small LLM only on "clarify".

SPEC 8.2: every reply gets one label from the calling prompt's allowed
set. A confused classifier coerces to "unclear" in code, so it can never
approve an Anki mutation by mistake.
"""

from __future__ import annotations

from langgraph.runtime import Runtime

from graph.context import RuntimeContext
from graph.helpers import PROMPT_LABELS, prepass_reply
from graph.state import State
from llm.system_prompts import reply_classifier_prompt


async def classify_label(prompt_kind: str, text: str, classifier) -> str:
    """Return one label from the prompt's allowed set. Offline-safe when the
    pre-pass decides (classifier untouched)."""
    label = prepass_reply(text, prompt_kind)
    if label != "clarify":
        return label

    result = await classifier.ainvoke(reply_classifier_prompt(prompt_kind, text))
    if result.label in PROMPT_LABELS[prompt_kind]:
        return result.label
    return "unclear"


async def classify_reply(state: State, runtime: Runtime[RuntimeContext]):
    label = await classify_label(
        state["reply_prompt"],
        state["last_reply"] or "",
        runtime.context.models.classifier,
    )
    return {"reply_intent": label}
