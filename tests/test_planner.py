import desiderist.actions  # noqa: F401 — registers built-in actions
from desiderist.actions.base import ActionContext
from desiderist.desires.store import DesireStore
from desiderist.harness.planner import dispatch_tool_calls, plan_next_actions
from desiderist.llm.base import LLMResponse, Message, Role, ToolCall
from desiderist.llm.fake import FakeLLMProvider
from desiderist.persistence.db import connect
from desiderist.persistence.repositories import ActionLogRepo, ConversationRepo, DesireEventRepo, DesireRepo


def make_harness_deps():
    conn = connect(":memory:")
    store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))
    conversations = ConversationRepo(conn)
    action_log = ActionLogRepo(conn)
    return store, conversations, action_log


def test_plan_next_actions_forces_tool_use():
    canned = LLMResponse(
        text=None,
        tool_calls=[ToolCall(id="t1", name="communicate_with_user", input={"message": "hi"})],
        stop_reason="tool_use",
        raw={},
    )
    provider = FakeLLMProvider(complete_responses=[canned])

    response = plan_next_actions(
        provider, active_desires=[], recent_turns=[Message(role=Role.USER, content="hello")]
    )

    assert response.stop_reason == "tool_use"
    assert provider.complete_calls[0]["tool_choice"] == "any"
    assert {t.name for t in provider.complete_calls[0]["tools"]} == {"communicate_with_user"}


def test_dispatch_tool_calls_executes_action_and_logs_it(capsys):
    store, conversations, action_log = make_harness_deps()
    turn = conversations.add_turn(role="user", content="hello")
    ctx = ActionContext(desire_store=store, conversation_repo=conversations, turn_id=turn["id"])

    tool_calls = [ToolCall(id="t1", name="communicate_with_user", input={"message": "hi there"})]
    results = dispatch_tool_calls(tool_calls, ctx=ctx, action_log=action_log)

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].requires_user_input is True

    captured = capsys.readouterr()
    assert "hi there" in captured.out

    logged = action_log.recent()
    assert len(logged) == 1
    assert logged[0]["action_name"] == "communicate_with_user"
    assert logged[0]["success"] == 1
