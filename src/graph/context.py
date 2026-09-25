from dataclasses import dataclass
from mcp import ClientSession
from application.config import Config
from llm.model import LLMModels
from infrastructure.anki import AnkiClient
from infrastructure.dictionary import DictionaryService

@dataclass(frozen=True, slots=True)
class RuntimeContext:
    mcp_session: ClientSession
    models: LLMModels
    dictionary: DictionaryService
    anki: AnkiClient
    config: Config