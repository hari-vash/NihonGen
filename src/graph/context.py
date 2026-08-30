from dataclasses import dataclass
from mcp import ClientSession
from llm.model import LLMModels

@dataclass(frozen=True, slots=True)
class RuntimeContext:
    mcp_session: ClientSession
    models: LLMModels