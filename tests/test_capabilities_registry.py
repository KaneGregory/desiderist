import asyncio
import threading
from contextlib import contextmanager

import desiderist.actions  # noqa: F401 — registers built-in actions
from desiderist.capabilities import registry as capabilities_registry
from desiderist.capabilities.mcp_action import McpToolAction


class _FakeManager:
    def __init__(self, actions):
        self._actions = actions

    async def snapshot_actions(self):
        return self._actions


@contextmanager
def _background_loop():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        yield loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)
        loop.close()


def test_all_actions_is_static_only_when_unconfigured():
    capabilities_registry.reset()
    names = {a.name for a in capabilities_registry.all_actions()}
    assert names == {"communicate_with_user"}


def test_all_actions_merges_static_and_dynamic():
    with _background_loop() as loop:
        dynamic_action = McpToolAction(
            provider_name="p", tool_name="t", description="d", input_schema={}, session=None, loop=loop
        )
        capabilities_registry.configure(_FakeManager([dynamic_action]), loop)
        try:
            names = {a.name for a in capabilities_registry.all_actions()}
            assert "communicate_with_user" in names
            assert "p__t" in names
            assert capabilities_registry.get_action("p__t") is dynamic_action
            assert any(spec.name == "p__t" for spec in capabilities_registry.to_tool_specs())
        finally:
            capabilities_registry.reset()


def test_get_action_raises_for_unknown_name():
    capabilities_registry.reset()
    try:
        capabilities_registry.get_action("does-not-exist")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
