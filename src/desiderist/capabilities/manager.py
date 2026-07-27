import asyncio
import contextlib
import json
import logging

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from desiderist.actions.base import Action
from desiderist.capabilities.mcp_action import McpToolAction
from desiderist.capabilities.models import ProviderStatus
from desiderist.daemon.bridge import HarnessBridge

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 15


class ProviderNotFoundError(RuntimeError):
    pass


class ProviderNotPendingError(RuntimeError):
    pass


class _LiveProvider:
    def __init__(self, name: str, session: ClientSession, tools: list[dict], task: asyncio.Task, stop_event: asyncio.Event):
        self.name = name
        self.session = session
        self.tools = tools
        self.task = task
        self.stop_event = stop_event


class CapabilityManager:
    """Owned by, and only ever driven from, the asyncio loop thread — it holds live
    ClientSessions, which aren't thread-safe. All persistence goes through the harness
    bridge, since the sqlite connection lives on a different thread."""

    def __init__(self, bridge: HarnessBridge, *, loop: asyncio.AbstractEventLoop):
        self._bridge = bridge
        self._loop = loop
        self._live: dict[str, _LiveProvider] = {}

    async def register(self, *, name: str, description: str, transport: dict, user_id: str = "local-user") -> dict:
        transport_json = json.dumps(transport)
        return await self._bridge.run(
            lambda: self._bridge.ctx.capabilities.register(
                name=name, description=description, transport_json=transport_json, user_id=user_id
            )
        )

    async def list_providers(self, *, user_id: str = "local-user") -> list[dict]:
        return await self._bridge.run(lambda: self._bridge.ctx.capabilities.list_all(user_id))

    async def get_provider(self, provider_id: str) -> dict | None:
        return await self._bridge.run(lambda: self._bridge.ctx.capabilities.get(provider_id))

    async def get_provider_detail(self, provider_id: str) -> dict | None:
        def _load() -> dict | None:
            provider = self._bridge.ctx.capabilities.get(provider_id)
            if provider is None:
                return None
            return {"provider": provider, "tools": self._bridge.ctx.capabilities.list_tools(provider_id)}

        return await self._bridge.run(_load)

    async def _own_connection(
        self, transport: dict, ready: asyncio.Future, stop_event: asyncio.Event
    ) -> None:
        """Runs as its own long-lived task for as long as a provider stays connected.
        mcp's stdio_client/ClientSession use anyio cancel scopes that must be entered
        and exited by the same task — approve()/revoke() are invoked from whatever
        short-lived per-connection task is handling that request, so the connection
        itself can't be owned by either of them; it needs one stable task of its own."""
        try:
            params = StdioServerParameters(command=transport["command"], args=transport.get("args", []))
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    if not ready.done():
                        ready.set_result((session, listed))
                    await stop_event.wait()
        except Exception as e:
            if not ready.done():
                ready.set_exception(e)
            else:
                logger.warning("live capability connection ended unexpectedly: %s", e)

    async def approve(self, provider_id: str) -> dict:
        provider = await self.get_provider(provider_id)
        if provider is None:
            raise ProviderNotFoundError(provider_id)
        if provider["status"] != ProviderStatus.PENDING.value:
            raise ProviderNotPendingError(f"Provider {provider_id} is {provider['status']}, not pending")

        transport = json.loads(provider["transport_json"])
        if transport.get("kind") != "stdio":
            raise ValueError(f"Unsupported transport kind: {transport.get('kind')}")

        ready: asyncio.Future = self._loop.create_future()
        stop_event = asyncio.Event()
        task = asyncio.create_task(self._own_connection(transport, ready, stop_event))

        try:
            session, listed = await asyncio.wait_for(ready, timeout=CONNECT_TIMEOUT_SECONDS)
        except Exception as e:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            await self._bridge.run(lambda: self._bridge.ctx.capabilities.record_error(provider_id, str(e)))
            raise

        tools = [
            {
                "tool_name": tool.name,
                "description": tool.description or "",
                "input_schema_json": json.dumps(tool.inputSchema),
            }
            for tool in listed.tools
        ]

        def _persist() -> dict:
            self._bridge.ctx.capabilities.replace_tools(provider_id, tools)
            self._bridge.ctx.capabilities.set_status(provider_id, ProviderStatus.APPROVED.value)
            self._bridge.ctx.capabilities.record_connected(provider_id)
            return self._bridge.ctx.capabilities.get(provider_id)

        updated = await self._bridge.run(_persist)
        self._live[provider_id] = _LiveProvider(
            name=provider["name"], session=session, tools=tools, task=task, stop_event=stop_event
        )
        return updated

    async def revoke(self, provider_id: str) -> dict:
        live = self._live.pop(provider_id, None)
        if live is not None:
            live.stop_event.set()
            await live.task

        def _persist() -> dict:
            self._bridge.ctx.capabilities.set_status(provider_id, ProviderStatus.REVOKED.value)
            return self._bridge.ctx.capabilities.get(provider_id)

        return await self._bridge.run(_persist)

    async def snapshot_actions(self) -> list[Action]:
        """Must only ever be awaited on the loop thread — either directly (daemon
        handlers already run there) or via `run_coroutine_threadsafe` from the harness
        thread (see capabilities/registry.py) — since it reads `self._live`, which this
        manager only ever mutates from that same thread."""
        actions: list[Action] = []
        for live in self._live.values():
            for tool in live.tools:
                actions.append(
                    McpToolAction(
                        provider_name=live.name,
                        tool_name=tool["tool_name"],
                        description=tool["description"],
                        input_schema=json.loads(tool["input_schema_json"]),
                        session=live.session,
                        loop=self._loop,
                    )
                )
        return actions
