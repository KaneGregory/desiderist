import ollama
from pydantic import BaseModel

from desiderist.llm.base import LLMProvider, LLMResponse, Message, ToolCall, ToolSpec


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        *,
        host: str = "http://localhost:11434",
        chat_model: str = "qwen2.5:14b-instruct",
        extraction_model: str = "qwen2.5:14b-instruct",
        planning_model: str = "qwen2.5:14b-instruct",
        client: ollama.Client | None = None,
    ):
        self._client = client or ollama.Client(host=host)
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
        ollama_messages = self._to_ollama_messages(messages, system)

        ollama_tools = None
        if tools:
            ollama_tools = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.input_schema},
                }
                for t in tools
            ]

        response = self._client.chat(
            model=model or self.chat_model,
            messages=ollama_messages,
            tools=ollama_tools,
        )

        message = response.message
        tool_calls = [
            ToolCall(id=f"call_{i}", name=tc.function.name, input=dict(tc.function.arguments))
            for i, tc in enumerate(message.tool_calls or [])
        ]
        return LLMResponse(
            text=message.content or None,
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
            raw=response.model_dump(mode="json"),
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
        ollama_messages = self._to_ollama_messages(messages, system)

        response = self._client.chat(
            model=model or self.extraction_model,
            messages=ollama_messages,
            format=schema.model_json_schema(),
        )
        return schema.model_validate_json(response.message.content)

    @staticmethod
    def _to_ollama_messages(messages: list[Message], system: str | None) -> list[dict]:
        ollama_messages = []
        if system is not None:
            ollama_messages.append({"role": "system", "content": system})
        ollama_messages.extend({"role": m.role.value, "content": m.content} for m in messages)
        return ollama_messages
