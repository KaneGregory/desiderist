import asyncio
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from desiderist.capabilities import registry as capabilities_registry
from desiderist.config import Settings
from desiderist.daemon import server as daemon_server
from desiderist.daemon.lifecycle import DaemonPaths
from desiderist.daemon.protocol import Request, Response, decode_response, encode
from desiderist.llm.fake import FakeLLMProvider


async def _call(sock_path: Path, command: str, **params) -> Response:
    reader, writer = await asyncio.open_unix_connection(str(sock_path))
    writer.write(encode(Request(id=str(uuid.uuid4()), command=command, params=params)))
    await writer.drain()
    line = await reader.readline()
    writer.close()
    await writer.wait_closed()
    return decode_response(line)


def test_daemon_serves_chat_desires_and_actions(monkeypatch):
    # pytest's tmp_path fixture nests deep enough on macOS to exceed AF_UNIX's ~104
    # char sockaddr_un limit, so a short /tmp-rooted dir is used directly instead.
    directory = Path(tempfile.mkdtemp())
    monkeypatch.setattr(daemon_server, "build_llm_provider", lambda settings: FakeLLMProvider())

    async def scenario():
        settings = Settings(db_path=directory / "desiderist.db")
        paths = DaemonPaths.for_dir(directory)
        stop_event = asyncio.Event()

        serve_task = asyncio.create_task(daemon_server._serve(paths, settings, stop_event=stop_event))
        try:
            deadline = time.monotonic() + 2.0
            while not paths.sock_path.exists() and time.monotonic() < deadline:
                await asyncio.sleep(0.02)
            assert paths.sock_path.exists()

            start_response = await _call(paths.sock_path, "chat.start")
            assert start_response.ok is True
            assert start_response.result["messages"]  # onboarding greeting for a fresh DB

            second_start = await _call(paths.sock_path, "chat.start")
            assert second_start.result["messages"] == []  # no repeat for a returning "user"

            desires_response = await _call(paths.sock_path, "desires.list")
            assert desires_response.ok is True
            assert len(desires_response.result["desires"]) == 1
            assert desires_response.result["desires"][0]["description"] == (
                "I want Desiderist to identify my initial desires"
            )

            history_response = await _call(
                paths.sock_path, "desires.history", desire_id=desires_response.result["desires"][0]["id"]
            )
            assert history_response.ok is True
            assert len(history_response.result["events"]) == 1

            actions_response = await _call(paths.sock_path, "actions.list")
            assert actions_response.ok is True
            assert actions_response.result["entries"][0]["action_name"] == "communicate_with_user"

            unknown_response = await _call(paths.sock_path, "not.a.real.command")
            assert unknown_response.ok is False
        finally:
            stop_event.set()
            await serve_task

    try:
        asyncio.run(scenario())
    finally:
        # capabilities.registry holds a process-global reference to this daemon's loop
        # and manager — without resetting it, a closed-loop reference would leak into
        # any later, unrelated test that calls all_actions()/to_tool_specs().
        capabilities_registry.reset()
        shutil.rmtree(directory, ignore_errors=True)
