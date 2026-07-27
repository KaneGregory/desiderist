import asyncio
import threading
from contextlib import contextmanager

from mcp.types import CallToolResult, TextContent

from desiderist.actions.base import ActionContext
from desiderist.capabilities.mcp_action import McpToolAction
from desiderist.desires.store import DesireStore
from desiderist.persistence.db import connect
from desiderist.persistence.repositories import ConversationRepo, DesireEventRepo, DesireRepo


class FakeCallSession:
    async def call_tool(self, name, arguments):
        return CallToolResult(content=[TextContent(type="text", text=f"called {name} with {arguments}")], isError=False)


class FailingSession:
    async def call_tool(self, name, arguments):
        raise RuntimeError("boom")


def _action_context() -> ActionContext:
    conn = connect(":memory:")
    store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))
    conversations = ConversationRepo(conn)
    return ActionContext(desire_store=store, conversation_repo=conversations, turn_id=None)


@contextmanager
def _background_loop():
    """Simulates the daemon's asyncio loop thread — a genuinely separate OS thread
    running its own event loop, distinct from the thread that calls execute()."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        yield loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)
        loop.close()


def test_execute_crosses_from_calling_thread_to_loop_thread():
    with _background_loop() as loop:
        action = McpToolAction(
            provider_name="p",
            tool_name="echo",
            description="d",
            input_schema={},
            session=FakeCallSession(),
            loop=loop,
        )

        # Called directly on this (test) thread — not the loop thread — mirroring how
        # the harness worker thread invokes it in the real daemon.
        result = action.execute({"text": "hi"}, _action_context())

    assert result.success is True
    assert "called echo" in result.output["text"]


def test_execute_returns_failure_result_instead_of_raising():
    with _background_loop() as loop:
        action = McpToolAction(
            provider_name="p", tool_name="x", description="d", input_schema={}, session=FailingSession(), loop=loop
        )
        result = action.execute({}, _action_context())

    assert result.success is False
    assert "boom" in result.output["error"]


def test_action_name_is_namespaced_by_provider():
    with _background_loop() as loop:
        action = McpToolAction(
            provider_name="thermostat",
            tool_name="set_temp",
            description="d",
            input_schema={},
            session=FakeCallSession(),
            loop=loop,
        )
    assert action.name == "thermostat__set_temp"
