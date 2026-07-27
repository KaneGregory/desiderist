import asyncio

from mcp import ClientSession
from mcp.types import CallToolResult

from desiderist.actions.base import ActionContext, ActionResult


def _content_to_output(result: CallToolResult) -> dict:
    texts = [block.text for block in result.content if getattr(block, "type", None) == "text"]
    output = {"content": [block.model_dump(mode="json") for block in result.content]}
    if texts:
        output["text"] = "\n".join(texts)
    return output


class McpToolAction:
    """Wraps one tool of one connected MCP provider as an Action. `execute()` runs on the
    harness worker thread but the session it drives lives on the asyncio loop thread —
    `run_coroutine_threadsafe` is the crossing point."""

    def __init__(
        self,
        *,
        provider_name: str,
        tool_name: str,
        description: str,
        input_schema: dict,
        session: ClientSession,
        loop: asyncio.AbstractEventLoop,
    ):
        self.name = f"{provider_name}__{tool_name}"
        self.description = description
        self.input_schema = input_schema
        self._tool_name = tool_name
        self._session = session
        self._loop = loop

    def execute(self, params: dict, ctx: ActionContext) -> ActionResult:
        try:
            future = asyncio.run_coroutine_threadsafe(self._session.call_tool(self._tool_name, params), self._loop)
            result = future.result(timeout=30)
        except Exception as e:
            return ActionResult(success=False, output={"error": str(e)})

        return ActionResult(success=not result.isError, output=_content_to_output(result))
