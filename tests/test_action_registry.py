import desiderist.actions  # noqa: F401 — registers built-in actions
from desiderist.actions.base import ActionContext
from desiderist.actions.registry import all_actions, get_action, to_tool_specs
from desiderist.desires.store import DesireStore
from desiderist.persistence.db import connect
from desiderist.persistence.repositories import ConversationRepo, DesireEventRepo, DesireRepo


def make_context(turn_id: str) -> ActionContext:
    conn = connect(":memory:")
    store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))
    conversations = ConversationRepo(conn)
    return ActionContext(desire_store=store, conversation_repo=conversations, turn_id=turn_id)


def test_communicate_with_user_action_is_registered():
    names = {a.name for a in all_actions()}
    assert "communicate_with_user" in names

    action = get_action("communicate_with_user")
    assert action.description
    assert action.input_schema["required"] == ["message"]


def test_to_tool_specs_includes_communicate_with_user():
    specs = to_tool_specs()
    names = {s.name for s in specs}
    assert "communicate_with_user" in names


def test_communicate_with_user_execute_prints_and_persists(capsys):
    action = get_action("communicate_with_user")
    ctx = make_context(turn_id="t1")

    result = action.execute({"message": "hello there"}, ctx)

    assert result.success is True
    assert result.requires_user_input is True

    captured = capsys.readouterr()
    assert "hello there" in captured.out

    recent = ctx.conversation_repo.recent()
    assert recent[-1]["role"] == "assistant"
    assert recent[-1]["content"] == "hello there"
