from desiderist.actions.base import ActionContext, ActionResult
from desiderist.actions.registry import get_action, to_tool_specs
from desiderist.desires.models import Desire
from desiderist.llm.base import LLMProvider, LLMResponse, Message, ToolCall
from desiderist.persistence.repositories import ActionLogRepo

PLANNING_SYSTEM_PROMPT = """\
You are the planning component of a harness that takes actions on behalf of a user in
order to fulfill their desires. Given the user's currently active desires and the recent
conversation, decide what action(s) to take next. You must call at least one of the
available actions — even a plain reply to the user is expressed by calling the
communicate_with_user action.
"""


def _format_active_desires(desires: list[Desire]) -> str:
    if not desires:
        return "(none)"
    return "\n".join(f"- [{d.id}] {d.description} (priority={d.priority})" for d in desires)


def plan_next_actions(
    provider: LLMProvider,
    *,
    active_desires: list[Desire],
    recent_turns: list[Message],
) -> LLMResponse:
    system = f"{PLANNING_SYSTEM_PROMPT}\nCurrently active desires:\n{_format_active_desires(active_desires)}"
    return provider.complete(recent_turns, system=system, tools=to_tool_specs(), tool_choice="any")


def dispatch_tool_calls(
    tool_calls: list[ToolCall],
    *,
    ctx: ActionContext,
    action_log: ActionLogRepo,
) -> list[ActionResult]:
    results = []
    for call in tool_calls:
        action = get_action(call.name)
        result = action.execute(call.input, ctx)
        action_log.add_entry(
            action_name=call.name,
            params=call.input,
            result=result.output,
            success=result.success,
            turn_id=ctx.turn_id,
        )
        results.append(result)
    return results
