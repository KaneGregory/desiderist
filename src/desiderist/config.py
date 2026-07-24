from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DESIDERIST_", populate_by_name=True)

    llm_provider: Literal["claude", "ollama"] | None = None

    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    db_path: Path = Field(default=Path.home() / ".desiderist" / "desiderist.db")

    chat_model: str = "claude-sonnet-5"
    extraction_model: str = "claude-sonnet-5"
    planning_model: str = "claude-sonnet-5"

    ollama_host: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:14b-instruct"
    ollama_extraction_model: str = "qwen2.5:14b-instruct"
    ollama_planning_model: str = "qwen2.5:14b-instruct"

    @property
    def resolved_provider(self) -> Literal["claude", "ollama"]:
        if self.llm_provider is not None:
            return self.llm_provider
        return "claude" if self.anthropic_api_key else "ollama"


def load_settings() -> Settings:
    return Settings()
