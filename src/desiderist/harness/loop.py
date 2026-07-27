import desiderist.actions  # noqa: F401 — registers built-in actions
from desiderist.actions.base import ActionContext, ActionResult
from desiderist.actions.communicate import COMMUNICATE_WITH_USER
from desiderist.desires.extraction import extract_desire_ops
from desiderist.desires.store import DesireStore
from desiderist.harness.planner import dispatch_tool_calls, plan_next_actions
from desiderist.llm.base import LLMProvider, LLMResponse, ToolCall, messages_from_turns
from desiderist.persistence.repositories import ActionLogRepo, ConversationRepo

RECENT_TURN_LIMIT = 20

ONBOARDING_MESSAGE = (
    "Hi — I'm Desiderist. Before anything else, I'd like to understand what you actually "
    "want: not just passing wants, but the outcomes you care about long-term. What are "
    "some things you're hoping for right now?"
)


def _with_fallback_reply(response: LLMResponse) -> LLMResponse:
    """Some providers (e.g. local models via Ollama) can't force tool use and may
    reply in plain text instead of calling an action. Treat that reply as an implicit
    call to communicate_with_user so every turn still produces a logged action."""
    if response.tool_calls or not response.text:
        return response
    return response.model_copy(
        update={
            "tool_calls": [
                ToolCall(id="fallback_reply", name=COMMUNICATE_WITH_USER, input={"message": response.text})
            ]
        }
    )


def run_turn(
    *,
    provider: LLMProvider,
    store: DesireStore,
    conversations: ConversationRepo,
    action_log: ActionLogRepo,
    user_message: str,
) -> list[ActionResult]:
    turn = conversations.add_turn(role="user", content=user_message)
    recent = messages_from_turns(conversations.recent(limit=RECENT_TURN_LIMIT))

    extraction = extract_desire_ops(
        provider,
        active_desires=store.active(),
        recent_turns=recent[:-1],
        new_message=user_message,
    )
    store.apply_ops(extraction.ops, turn_id=turn["id"], raw_llm_response=extraction.model_dump_json())

    all_results: list[ActionResult] = []
    while True:
        response = _with_fallback_reply(plan_next_actions(provider, active_desires=store.active(), recent_turns=recent))
        ctx = ActionContext(desire_store=store, conversation_repo=conversations, turn_id=turn["id"])
        results = dispatch_tool_calls(response.tool_calls, ctx=ctx, action_log=action_log)
        all_results.extend(results)

        if not results or any(r.requires_user_input for r in results):
            break

        recent = messages_from_turns(conversations.recent(limit=RECENT_TURN_LIMIT))

    return all_results


def run_onboarding(
    *,
    store: DesireStore,
    conversations: ConversationRepo,
    action_log: ActionLogRepo,
    user_id: str = "local-user",
) -> list[ActionResult] | None:
    """Skips the LLM planner entirely — there's no conversation yet for it to plan over."""
    desire = store.seed_onboarding_desire(user_id=user_id)
    if desire is None:
        return None

    call = ToolCall(id="onboarding", name=COMMUNICATE_WITH_USER, input={"message": ONBOARDING_MESSAGE})
    ctx = ActionContext(desire_store=store, conversation_repo=conversations, turn_id=None)
    return dispatch_tool_calls([call], ctx=ctx, action_log=action_log)
