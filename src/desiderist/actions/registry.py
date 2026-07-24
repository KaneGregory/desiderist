from desiderist.actions.base import Action
from desiderist.llm.base import ToolSpec

_REGISTRY: dict[str, Action] = {}


def register_action(action):
    instance = action() if isinstance(action, type) else action
    _REGISTRY[instance.name] = instance
    return action


def all_actions() -> list[Action]:
    return list(_REGISTRY.values())


def get_action(name: str) -> Action:
    return _REGISTRY[name]


def to_tool_specs() -> list[ToolSpec]:
    return [ToolSpec(name=a.name, description=a.description, input_schema=a.input_schema) for a in all_actions()]
