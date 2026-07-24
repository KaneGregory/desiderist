from pydantic import BaseModel

from desiderist.llm.base import LLMResponse, Message, Role, ToolCall
from desiderist.llm.fake import FakeLLMProvider


class Extracted(BaseModel):
    value: str


def test_fake_provider_complete_returns_queued_response():
    response = LLMResponse(text="hi there", tool_calls=[], stop_reason="end_turn", raw={})
    provider = FakeLLMProvider(complete_responses=[response])

    result = provider.complete([Message(role=Role.USER, content="hello")])

    assert result.text == "hi there"
    assert len(provider.complete_calls) == 1
    assert provider.complete_calls[0]["messages"][0].content == "hello"


def test_fake_provider_complete_returns_tool_call():
    response = LLMResponse(
        text=None,
        tool_calls=[ToolCall(id="t1", name="communicate_with_user", input={"message": "hi"})],
        stop_reason="tool_use",
        raw={},
    )
    provider = FakeLLMProvider(complete_responses=[response])

    result = provider.complete([Message(role=Role.USER, content="hello")], tool_choice="any")

    assert result.stop_reason == "tool_use"
    assert result.tool_calls[0].name == "communicate_with_user"


def test_fake_provider_extract_structured_returns_queued_model():
    provider = FakeLLMProvider(extraction_responses=[Extracted(value="wants coffee")])

    result = provider.extract_structured(
        [Message(role=Role.USER, content="I want coffee")], system="extract", schema=Extracted
    )

    assert result.value == "wants coffee"
    assert provider.extraction_calls[0]["schema"] is Extracted
