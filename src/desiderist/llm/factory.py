from desiderist.config import Settings
from desiderist.llm.base import LLMProvider
from desiderist.llm.claude import ClaudeProvider
from desiderist.llm.ollama_provider import OllamaProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.resolved_provider == "claude":
        if not settings.anthropic_api_key:
            raise RuntimeError("llm_provider is 'claude' but ANTHROPIC_API_KEY is not set.")
        return ClaudeProvider(
            api_key=settings.anthropic_api_key,
            chat_model=settings.chat_model,
            extraction_model=settings.extraction_model,
            planning_model=settings.planning_model,
        )

    return OllamaProvider(
        host=settings.ollama_host,
        chat_model=settings.ollama_chat_model,
        extraction_model=settings.ollama_extraction_model,
        planning_model=settings.ollama_planning_model,
    )
