from desiderist.daemon.bridge import HarnessContext
from desiderist.harness.loop import run_onboarding, run_turn


def chat_start(ctx: HarnessContext) -> dict:
    replies: list[str] = []
    run_onboarding(store=ctx.store, conversations=ctx.conversations, action_log=ctx.action_log, reply_sink=replies.append)
    return {"messages": replies}


def chat_send(ctx: HarnessContext, message: str) -> dict:
    replies: list[str] = []
    run_turn(
        provider=ctx.provider,
        store=ctx.store,
        conversations=ctx.conversations,
        action_log=ctx.action_log,
        user_message=message,
        reply_sink=replies.append,
    )
    return {"messages": replies}


def desires_list(ctx: HarnessContext, *, show_all: bool = False) -> dict:
    desires = ctx.store.all() if show_all else ctx.store.active()
    return {"desires": [d.model_dump(mode="json") for d in desires]}


def desires_history(ctx: HarnessContext, *, desire_id: str) -> dict:
    return {"events": ctx.store.history(desire_id)}


def actions_list(ctx: HarnessContext, *, limit: int = 20) -> dict:
    return {"entries": ctx.action_log.recent(limit=limit)}
