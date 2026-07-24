from ollama._types import ChatResponse, Message as OllamaMessage
from pydantic import BaseModel

from desiderist.llm.base import Message, Role
from desiderist.llm.ollama_provider import OllamaProvider


class StubClient:
    def __init__(self, response: ChatResponse):
        self._response = response
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class Extracted(BaseModel):
    value: str


def test_complete_translates_tool_call_into_llm_response():
    response = ChatResponse(
        model="qwen2.5:14b-instruct",
        message=OllamaMessage(
            role="assistant",
            content=None,
            tool_calls=[
                OllamaMessage.ToolCall(
                    function=OllamaMessage.ToolCall.Function(
                        name="communicate_with_user", arguments={"message": "hi"}
                    )
                )
            ],
        ),
    )
    client = StubClient(response)
    provider = OllamaProvider(client=client)

    result = provider.complete([Message(role=Role.USER, content="hello")], tool_choice="any")

    assert result.stop_reason == "tool_use"
    assert result.tool_calls[0].name == "communicate_with_user"
    assert result.tool_calls[0].input == {"message": "hi"}
    assert client.calls[0]["model"] == "qwen2.5:14b-instruct"


def test_complete_with_no_tool_call_returns_plain_text():
    response = ChatResponse(
        model="qwen2.5:14b-instruct",
        message=OllamaMessage(role="assistant", content="just chatting"),
    )
    client = StubClient(response)
    provider = OllamaProvider(client=client)

    result = provider.complete([Message(role=Role.USER, content="hello")])

    assert result.text == "just chatting"
    assert result.tool_calls == []
    assert result.stop_reason == "end_turn"


def test_extract_structured_parses_schema_constrained_json():
    response = ChatResponse(
        model="qwen2.5:14b-instruct",
        message=OllamaMessage(role="assistant", content='{"value": "wants coffee"}'),
    )
    client = StubClient(response)
    provider = OllamaProvider(client=client)

    result = provider.extract_structured(
        [Message(role=Role.USER, content="I want coffee")], system="extract", schema=Extracted
    )

    assert result.value == "wants coffee"
    assert client.calls[0]["format"] == Extracted.model_json_schema()
