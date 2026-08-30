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


def normalize_yes_no(text: str) -> str:
    """
    Convert common natural-language confirmations/rejections into:
        approve
        reject
        clarify
    """

    normalized = re.sub(r"\s+", " ", text.strip().lower())

    normalized = normalized.replace("’", "'")
    normalized = normalized.replace(".", "")
    normalized = normalized.replace(",", "")

    positive_phrases = {"yes","yeah","yep","yup","sure","absolutely","definitely","go ahead","let's go","lets go","ready","okay","ok","sounds good","do it","please do","i'm ready","im ready","yes please","okay please"}

    negative_phrases = {"no","nope","not yet","i don't understand","i dont understand","i still don't understand","i still dont understand","i have doubts","i have a doubt","explain more","explain again","please explain","i'm confused","im confused","i don't get it","i dont get it"}

    if normalized in positive_phrases:
        return "approve"

    if normalized in negative_phrases:
        return "reject"

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