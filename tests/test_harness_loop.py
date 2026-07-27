import desiderist.actions  # noqa: F401 — registers built-in actions
from desiderist.desires.models import ExtractionResult
from desiderist.desires.store import DesireStore
from desiderist.harness.loop import run_onboarding, run_turn
from desiderist.llm.base import LLMResponse, ToolCall
from desiderist.llm.fake import FakeLLMProvider
from desiderist.persistence.db import connect
from desiderist.persistence.repositories import ActionLogRepo, ConversationRepo, DesireEventRepo, DesireRepo


def test_run_turn_extracts_desire_plans_and_executes_action(capsys):
    conn = connect(":memory:")
    store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))
    conversations = ConversationRepo(conn)
    action_log = ActionLogRepo(conn)

    provider = FakeLLMProvider(
        extraction_responses=[
            ExtractionResult(ops=[{"op": "create", "description": "wants coffee", "reasoning": "asked for coffee"}])
        ],
        complete_responses=[
            LLMResponse(
                text=None,
                tool_calls=[
                    ToolCall(id="t1", name="communicate_with_user", input={"message": "Sure, one coffee coming up!"})
                ],
                stop_reason="tool_use",
                raw={},
            )
        ],
    )

    results = run_turn(
        provider=provider,
        store=store,
        conversations=conversations,
        action_log=action_log,
        user_message="I'd like a coffee",
    )

    assert len(results) == 1
    assert results[0].requires_user_input is True

    active = store.active()
    assert len(active) == 1
    assert active[0].description == "wants coffee"

    captured = capsys.readouterr()
    assert "Sure, one coffee coming up!" in captured.out

    logged = action_log.recent()
    assert len(logged) == 1
    assert logged[0]["action_name"] == "communicate_with_user"

    turns = conversations.recent()
    assert turns[0]["role"] == "user"
    assert turns[-1]["role"] == "assistant"
    assert turns[-1]["content"] == "Sure, one coffee coming up!"


def test_run_turn_stops_after_first_action_requiring_user_input(capsys):
    conn = connect(":memory:")
    store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))
    conversations = ConversationRepo(conn)
    action_log = ActionLogRepo(conn)

    provider = FakeLLMProvider(
        extraction_responses=[ExtractionResult(ops=[])],
        complete_responses=[
            LLMResponse(
                text=None,
                tool_calls=[ToolCall(id="t1", name="communicate_with_user", input={"message": "first"})],
                stop_reason="tool_use",
                raw={},
            ),
            LLMResponse(
                text=None,
                tool_calls=[ToolCall(id="t2", name="communicate_with_user", input={"message": "second"})],
                stop_reason="tool_use",
                raw={},
            ),
        ],
    )

    results = run_turn(
        provider=provider,
        store=store,
        conversations=conversations,
        action_log=action_log,
        user_message="hello",
    )

    # communicate_with_user always sets requires_user_input=True, so the loop
    # should stop after the first planning pass.
    assert len(results) == 1
    assert len(provider.complete_calls) == 1


def test_run_onboarding_seeds_desire_and_prompts_user_with_no_llm_call(capsys):
    conn = connect(":memory:")
    store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))
    conversations = ConversationRepo(conn)
    action_log = ActionLogRepo(conn)

    results = run_onboarding(store=store, conversations=conversations, action_log=action_log)

    assert len(results) == 1
    assert results[0].requires_user_input is True

    active = store.active()
    assert len(active) == 1
    assert active[0].description == "I want Desiderist to identify my initial desires"

    captured = capsys.readouterr()
    assert captured.out.strip() != ""

    turns = conversations.recent()
    assert len(turns) == 1
    assert turns[0]["role"] == "assistant"

    logged = action_log.recent()
    assert len(logged) == 1
    assert logged[0]["action_name"] == "communicate_with_user"


def test_run_onboarding_is_noop_for_returning_user():
    conn = connect(":memory:")
    store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))
    conversations = ConversationRepo(conn)
    action_log = ActionLogRepo(conn)

    provider = FakeLLMProvider(
        extraction_responses=[
            ExtractionResult(ops=[{"op": "create", "description": "wants coffee", "reasoning": "r"}])
        ],
        complete_responses=[
            LLMResponse(
                text=None,
                tool_calls=[ToolCall(id="t1", name="communicate_with_user", input={"message": "sure"})],
                stop_reason="tool_use",
                raw={},
            )
        ],
    )
    run_turn(
        provider=provider,
        store=store,
        conversations=conversations,
        action_log=action_log,
        user_message="I'd like a coffee",
    )

    results = run_onboarding(store=store, conversations=conversations, action_log=action_log)

    assert results is None
    assert len(store.all()) == 1
    assert len(action_log.recent()) == 1


def test_run_turn_falls_back_to_communicate_when_no_tool_call_is_made(capsys):
    conn = connect(":memory:")
    store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))
    conversations = ConversationRepo(conn)
    action_log = ActionLogRepo(conn)

    provider = FakeLLMProvider(
        extraction_responses=[ExtractionResult(ops=[])],
        complete_responses=[
            LLMResponse(text="just chatting, no tool call here", tool_calls=[], stop_reason="end_turn", raw={})
        ],
    )

    results = run_turn(
        provider=provider,
        store=store,
        conversations=conversations,
        action_log=action_log,
        user_message="hello",
    )

    assert len(results) == 1
    assert results[0].requires_user_input is True

    captured = capsys.readouterr()
    assert "just chatting, no tool call here" in captured.out

    logged = action_log.recent()
    assert logged[0]["action_name"] == "communicate_with_user"
