"""Reply classification: deterministic pre-pass first, small LLM only on "clarify".

SPEC 8.2: every reply gets one label from the calling prompt's allowed
set. A confused classifier coerces to "unclear" in code, so it can never
approve an Anki mutation by mistake.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from langgraph.runtime import Runtime

from graph.context import RuntimeContext
from graph.helpers import PROMPT_LABELS, prepass_reply
from graph.state import State
from llm.system_prompts import reply_classifier_prompt

REPLY_LOG_PATH = Path(__file__).resolve().parents[3] / "evals" / "reply_log.jsonl"


def _log_reply(prompt_kind: str, text: str, prepass: str, final: str) -> None:
    REPLY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt_kind,
        "text": text,
        "prepass": prepass,
        "final": final,
    }
    with open(REPLY_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def classify_label(prompt_kind: str, text: str, classifier) -> str:
    """Return one label from the prompt's allowed set. Offline-safe when the
    pre-pass decides (classifier untouched). Every verdict is logged."""
    prepass = prepass_reply(text, prompt_kind)
    if prepass != "clarify":
        _log_reply(prompt_kind, text, prepass, prepass)
        return prepass

    result = await classifier.ainvoke(reply_classifier_prompt(prompt_kind, text))
    final = result.label if result.label in PROMPT_LABELS[prompt_kind] else "unclear"
    _log_reply(prompt_kind, text, prepass, final)
    return final


async def classify_reply(state: State, runtime: Runtime[RuntimeContext]):
    label = await classify_label(
        state["reply_prompt"],
        state["last_reply"] or "",
        runtime.context.models.classifier,
    )
    return {"reply_intent": label}
