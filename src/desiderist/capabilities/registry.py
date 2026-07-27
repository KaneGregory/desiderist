import asyncio

from desiderist.actions import registry as static_registry
from desiderist.actions.base import Action
from desiderist.capabilities.manager import CapabilityManager
from desiderist.llm.base import ToolSpec

_manager: CapabilityManager | None = None
_loop: asyncio.AbstractEventLoop | None = None


def configure(manager: CapabilityManager, loop: asyncio.AbstractEventLoop) -> None:
    """Called once by the daemon at startup, after the manager and its loop exist."""
    global _manager, _loop
    _manager = manager
    _loop = loop


def reset() -> None:
    """Clears configuration — tests must call this after a daemon they started shuts
    down, since a stale loop reference left behind would break any later, unrelated
    caller of `all_actions()`/`to_tool_specs()` in the same process."""
    global _manager, _loop
    _manager = None
    _loop = None


def _dynamic_actions() -> list[Action]:
    if _manager is None:
        return []
    # Crosses onto the loop thread that owns the manager's live sessions — this
    # function is only ever called from the harness thread (via planner.py).
    future = asyncio.run_coroutine_threadsafe(_manager.snapshot_actions(), _loop)
    return future.result(timeout=5)


def all_actions() -> list[Action]:
    return static_registry.all_actions() + _dynamic_actions()


def get_action(name: str) -> Action:
    try:
        return static_registry.get_action(name)
    except KeyError:
        pass
    for action in _dynamic_actions():
        if action.name == name:
            return action
    raise KeyError(name)


def to_tool_specs() -> list[ToolSpec]:
    return [ToolSpec(name=a.name, description=a.description, input_schema=a.input_schema) for a in all_actions()]
