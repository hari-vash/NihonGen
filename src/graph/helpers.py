import json
import re


def parse_mcp_json(result) -> dict:
    """Parse the JSON payload returned by an MCP tool."""
    if not result.content:
        raise RuntimeError("MCP server returned no content.")

    first_content = result.content[0]
    if not hasattr(first_content, "text"):
        raise RuntimeError("MCP server returned non-text content.")

    try:
        return json.loads(first_content.text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("MCP server returned invalid JSON.") from exc


PROMPT_LABELS = {
    "quiz_readiness": {"ready", "not_ready", "question", "stop", "unclear"},
    "quiz_answer": {"answer", "dont_know", "question", "skip_kanji", "stop", "unclear"},
    "anki_approval": {"approve", "decline", "question", "stop", "unclear"},
}

_READY_PHRASES = {
    "yes", "yeah", "yep", "yup", "sure", "absolutely", "definitely",
    "go ahead", "let's go", "lets go", "ready", "okay", "ok",
    "sounds good", "do it", "please do", "i'm ready", "im ready",
    "yes please", "okay please",
}

_NOT_READY_PHRASES = {
    "no", "nope", "not yet", "i don't understand", "i dont understand",
    "i still don't understand", "i still dont understand", "i have doubts",
    "i have a doubt", "explain more", "explain again", "please explain",
    "i'm confused", "im confused", "i don't get it", "i dont get it",
}

_DONT_KNOW_PHRASES = {
    "i don't know", "i dont know", "idk", "no idea", "i have no idea",
    "not sure", "dunno",
}

_SKIP_PHRASES = {
    "skip", "skip this", "skip this kanji", "skip kanji", "next",
    "next kanji", "move on",
}

_STOP_PHRASES = {
    "stop", "quit", "exit", "end session", "stop session", "finish",
}

_KANJI_RE = re.compile(r"[\u4e00-\u9faf]")

_QUESTION_STARTERS = ("what", "why", "how", "when", "where", "which", "who", "can you", "could you")


def extract_kanji_ordered(text: str) -> list[str]:
    """Kanji in first-appearance order, deduped. Shared with typed input
    (FR-2). Mirrors mcp_server.py's pattern; A9's wider-range limits apply."""
    seen: list[str] = []
    for char in _KANJI_RE.findall(text):
        if char not in seen:
            seen.append(char)
    return seen


HELP_TEXTS = {
    "quiz_readiness": "tip: reply yes or no — or ask a question, or type stop.",
    "quiz_answer": "tip: answer the question, or type i don't know / skip / stop — questions welcome.",
    "anki_approval": "tip: reply yes or no — conditions like 'only the readings' will be re-asked. stop ends here.",
}

_INTERRUPT_TO_PROMPT = {
    "quiz_readiness": "quiz_readiness",
    "quiz_answer": "quiz_answer",
    "anki_update_approval": "anki_approval",
    "anki_create_approval": "anki_approval",
}


def hint_for_interrupt(interrupt_type: str) -> str:
    """One-line hint for an interrupt payload. Empty string when unknown."""
    prompt = _INTERRUPT_TO_PROMPT.get(interrupt_type, "")
    return HELP_TEXTS.get(prompt, "")


def _normalize_reply(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    normalized = normalized.replace("’", "'")
    normalized = normalized.replace(".", "")
    normalized = normalized.replace(",", "")
    return normalized


def prepass_reply(text: str, prompt: str) -> str:
    """Deterministic reply pre-pass. Returns a label from the prompt's
    allowed set, or "clarify" when only the LLM classifier can decide."""
    allowed = PROMPT_LABELS[prompt]
    normalized = _normalize_reply(text)

    if normalized in _STOP_PHRASES and "stop" in allowed:
        return "stop"

    if normalized in _SKIP_PHRASES and "skip_kanji" in allowed:
        return "skip_kanji"

    if normalized in _DONT_KNOW_PHRASES and "dont_know" in allowed:
        return "dont_know"

    if normalized in _READY_PHRASES:
        for label in ("ready", "approve"):
            if label in allowed:
                return label

    if normalized in _NOT_READY_PHRASES:
        for label in ("not_ready", "decline"):
            if label in allowed:
                return label

    if (
        "question" in allowed
        and (normalized.endswith("?")
             or normalized == "help"
             or normalized.startswith(_QUESTION_STARTERS))
    ):
        return "question"

    return "clarify"

from langchain_core.messages import BaseMessage


def message_to_text(message: BaseMessage) -> str:
    """Extract human-readable text from a LangChain message."""
    content = message.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []

        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue

            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))

        return "".join(parts)

    return str(content)