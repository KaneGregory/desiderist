from pydantic import BaseModel

from desiderist.llm.base import LLMResponse, Message, ToolSpec


class FakeLLMProvider:
    def __init__(
        self,
        complete_responses: list[LLMResponse] | None = None,
        extraction_responses: list[BaseModel] | None = None,
    ):
        self._complete_responses = list(complete_responses or [])
        self._extraction_responses = list(extraction_responses or [])
        self.complete_calls: list[dict] = []
        self.extraction_calls: list[dict] = []

    def complete(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
        tool_choice: str = "auto",
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self.complete_calls.append(
            {"messages": messages, "system": system, "tools": tools, "tool_choice": tool_choice}
        )
        return self._complete_responses.pop(0)

    def extract_structured(
        self,
        messages: list[Message],
        *,
        system: str | None,
        schema: type[BaseModel],
        max_tokens: int = 4096,
    ) -> BaseModel:
        self.extraction_calls.append({"messages": messages, "system": system, "schema": schema})
        return self._extraction_responses.pop(0)
