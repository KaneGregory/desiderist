import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from desiderist.capabilities import manager as manager_module
from desiderist.capabilities.manager import CapabilityManager, ProviderNotFoundError, ProviderNotPendingError
from desiderist.capabilities.models import ProviderStatus
from desiderist.daemon.bridge import HarnessBridge
from desiderist.llm.fake import FakeLLMProvider


@asynccontextmanager
async def _fake_stdio_client(params):
    yield ("read-stream", "write-stream")


class FakeSession:
    def __init__(self):
        self.tools: list = []
        self.closed = False

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        self.closed = True
        return False

    async def initialize(self) -> None:
        return None

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools)


def _patch_mcp(monkeypatch, session: FakeSession) -> None:
    monkeypatch.setattr(manager_module, "stdio_client", lambda params: _fake_stdio_client(params))
    monkeypatch.setattr(manager_module, "ClientSession", lambda read, write: session)


def _transport() -> dict:
    return {"kind": "stdio", "command": "python", "args": ["server.py"]}


def test_register_creates_pending_provider():
    async def scenario():
        bridge = HarnessBridge(":memory:", FakeLLMProvider())
        manager = CapabilityManager(bridge, loop=asyncio.get_running_loop())

        provider = await manager.register(name="thermostat", description="A smart thermostat", transport=_transport())
        assert provider["status"] == ProviderStatus.PENDING.value
        assert provider["name"] == "thermostat"

        listed = await manager.list_providers()
        assert len(listed) == 1
        assert listed[0]["id"] == provider["id"]

    asyncio.run(scenario())


def test_approve_connects_and_records_tools(monkeypatch):
    session = FakeSession()
    session.tools = [
        SimpleNamespace(
            name="set_temp", description="Set the target temperature", inputSchema={"type": "object", "properties": {}}
        )
    ]
    _patch_mcp(monkeypatch, session)

    async def scenario():
        bridge = HarnessBridge(":memory:", FakeLLMProvider())
        manager = CapabilityManager(bridge, loop=asyncio.get_running_loop())

        provider = await manager.register(name="thermostat", description="d", transport=_transport())
        approved = await manager.approve(provider["id"])
        assert approved["status"] == ProviderStatus.APPROVED.value

        actions = await manager.snapshot_actions()
        assert len(actions) == 1
        assert actions[0].name == "thermostat__set_temp"

        detail = await manager.get_provider_detail(provider["id"])
        assert len(detail["tools"]) == 1
        assert detail["tools"][0]["tool_name"] == "set_temp"

    asyncio.run(scenario())


def test_approve_twice_raises_not_pending(monkeypatch):
    _patch_mcp(monkeypatch, FakeSession())

    async def scenario():
        bridge = HarnessBridge(":memory:", FakeLLMProvider())
        manager = CapabilityManager(bridge, loop=asyncio.get_running_loop())
        provider = await manager.register(name="p", description="d", transport=_transport())
        await manager.approve(provider["id"])

        try:
            await manager.approve(provider["id"])
            raise AssertionError("expected ProviderNotPendingError")
        except ProviderNotPendingError:
            pass

    asyncio.run(scenario())


def test_approve_unknown_provider_raises_not_found():
    async def scenario():
        bridge = HarnessBridge(":memory:", FakeLLMProvider())
        manager = CapabilityManager(bridge, loop=asyncio.get_running_loop())
        try:
            await manager.approve("nonexistent")
            raise AssertionError("expected ProviderNotFoundError")
        except ProviderNotFoundError:
            pass

    asyncio.run(scenario())


def test_register_never_connects_before_approval(monkeypatch):
    calls: list[str] = []

    def _tracking_stdio_client(params):
        calls.append("connected")
        return _fake_stdio_client(params)

    monkeypatch.setattr(manager_module, "stdio_client", _tracking_stdio_client)

    async def scenario():
        bridge = HarnessBridge(":memory:", FakeLLMProvider())
        manager = CapabilityManager(bridge, loop=asyncio.get_running_loop())
        await manager.register(name="p", description="d", transport=_transport())
        assert calls == []  # registration alone must never contact the provider

    asyncio.run(scenario())


def test_revoke_closes_session_and_removes_from_snapshot(monkeypatch):
    session = FakeSession()
    session.tools = [SimpleNamespace(name="ping", description="ping", inputSchema={"type": "object"})]
    _patch_mcp(monkeypatch, session)

    async def scenario():
        bridge = HarnessBridge(":memory:", FakeLLMProvider())
        manager = CapabilityManager(bridge, loop=asyncio.get_running_loop())
        provider = await manager.register(name="p", description="d", transport=_transport())
        await manager.approve(provider["id"])
        assert len(await manager.snapshot_actions()) == 1

        revoked = await manager.revoke(provider["id"])
        assert revoked["status"] == ProviderStatus.REVOKED.value
        assert session.closed is True
        assert await manager.snapshot_actions() == []

    asyncio.run(scenario())
