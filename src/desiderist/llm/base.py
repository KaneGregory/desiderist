from enum import Enum
from typing import Protocol

from pydantic import BaseModel


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    role: Role
    content: str


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict


class ToolCall(BaseModel):
    id: str
    name: str
    input: dict


class LLMResponse(BaseModel):
    text: str | None
    tool_calls: list[ToolCall]
    stop_reason: str
    raw: dict


def messages_from_turns(turns: list[dict]) -> list["Message"]:
    return [Message(role=Role(t["role"]), content=t["content"]) for t in turns]


class LLMProvider(Protocol):
    def complete(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
        tool_choice: str = "auto",
        max_tokens: int = 4096,
    ) -> LLMResponse: ...

    def extract_structured(
        self,
        messages: list[Message],
        *,
        system: str | None,
        schema: type[BaseModel],
        max_tokens: int = 4096,
    ) -> BaseModel: ...
