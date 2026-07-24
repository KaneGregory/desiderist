import anthropic
from pydantic import BaseModel

from desiderist.llm.base import LLMProvider, LLMResponse, Message, ToolCall, ToolSpec


class ClaudeProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        *,
        chat_model: str = "claude-sonnet-5",
        extraction_model: str = "claude-sonnet-5",
        planning_model: str = "claude-sonnet-5",
    ):
        self._client = anthropic.Anthropic(api_key=api_key)
        self.chat_model = chat_model
        self.extraction_model = extraction_model
        self.planning_model = planning_model

    def complete(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
        tool_choice: str = "auto",
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> LLMResponse:
        kwargs = {}
        if system is not None:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools
            ]
            kwargs["tool_choice"] = {"type": tool_choice}

        response = self._client.messages.create(
            model=model or self.chat_model,
            max_tokens=max_tokens,
            messages=[{"role": m.role.value, "content": m.content} for m in messages],
            **kwargs,
        )

        text = next((b.text for b in response.content if b.type == "text"), None)
        tool_calls = [
            ToolCall(id=b.id, name=b.name, input=b.input) for b in response.content if b.type == "tool_use"
        ]
        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            raw=response.to_dict(),
        )

    def extract_structured(
        self,
        messages: list[Message],
        *,
        system: str | None,
        schema: type[BaseModel],
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> BaseModel:
        kwargs = {}
        if system is not None:
            kwargs["system"] = system

        response = self._client.messages.parse(
            model=model or self.extraction_model,
            max_tokens=max_tokens,
            messages=[{"role": m.role.value, "content": m.content} for m in messages],
            output_format=schema,
            **kwargs,
        )
        return response.parsed_output
