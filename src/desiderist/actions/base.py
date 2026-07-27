from typing import Callable, Protocol

from pydantic import BaseModel, ConfigDict

from desiderist.desires.store import DesireStore
from desiderist.persistence.repositories import ConversationRepo


class ActionResult(BaseModel):
    success: bool
    output: dict
    requires_user_input: bool = False


class ActionContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    desire_store: DesireStore
    conversation_repo: ConversationRepo
    turn_id: str | None
    reply_sink: Callable[[str], None] = print


class Action(Protocol):
    name: str
    description: str
    input_schema: dict

    def execute(self, params: dict, ctx: ActionContext) -> ActionResult: ...
