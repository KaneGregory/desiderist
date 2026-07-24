from desiderist.cli import turns_to_messages
from desiderist.llm.base import Role


def test_turns_to_messages_converts_role_and_content():
    turns = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]

    messages = turns_to_messages(turns)

    assert messages[0].role == Role.USER
    assert messages[0].content == "hi"
    assert messages[1].role == Role.ASSISTANT
    assert messages[1].content == "hello"
