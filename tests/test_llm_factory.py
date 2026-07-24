import pytest

from desiderist.config import Settings
from desiderist.llm.claude import ClaudeProvider
from desiderist.llm.factory import build_llm_provider
from desiderist.llm.ollama_provider import OllamaProvider


def test_defaults_to_ollama_when_no_api_key():
    settings = Settings(_env_file=None, anthropic_api_key=None)
    assert settings.resolved_provider == "ollama"
    assert isinstance(build_llm_provider(settings), OllamaProvider)


def test_uses_claude_when_api_key_present():
    settings = Settings(_env_file=None, anthropic_api_key="sk-test")
    assert settings.resolved_provider == "claude"
    assert isinstance(build_llm_provider(settings), ClaudeProvider)


def test_explicit_provider_overrides_api_key_presence():
    settings = Settings(_env_file=None, anthropic_api_key="sk-test", llm_provider="ollama")
    assert settings.resolved_provider == "ollama"
    assert isinstance(build_llm_provider(settings), OllamaProvider)


def test_claude_without_api_key_raises():
    settings = Settings(_env_file=None, anthropic_api_key=None, llm_provider="claude")
    with pytest.raises(RuntimeError):
        build_llm_provider(settings)
