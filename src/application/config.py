from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Deployment settings (not workflow data). See docs/SPEC.md section 10."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anki_deck: str = "Test_Deck1"
    anki_url: str = "http://127.0.0.1:8765"
