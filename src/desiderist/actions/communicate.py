from desiderist.actions.base import ActionContext, ActionResult
from desiderist.actions.registry import register_action

COMMUNICATE_WITH_USER = "communicate_with_user"


@register_action
class CommunicateWithUserAction:
    name = COMMUNICATE_WITH_USER
    description = "Send a message to the user via their current channel (CLI)."
    input_schema = {
        "type": "object",
        "properties": {"message": {"type": "string", "description": "The message to show the user."}},
        "required": ["message"],
        "additionalProperties": False,
    }

    def execute(self, params: dict, ctx: ActionContext) -> ActionResult:
        ctx.reply_sink(params["message"])
        ctx.conversation_repo.add_turn(role="assistant", content=params["message"])
        return ActionResult(success=True, output={}, requires_user_input=True)
