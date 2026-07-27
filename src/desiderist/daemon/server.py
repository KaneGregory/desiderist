import asyncio
import logging
import os
import signal
from typing import Awaitable, Callable

from desiderist.config import Settings, load_settings
from desiderist.daemon import handlers
from desiderist.daemon.bridge import HarnessBridge
from desiderist.daemon.lifecycle import DaemonLock, DaemonPaths, write_pid_file
from desiderist.daemon.protocol import Request, Response, decode_request, encode
from desiderist.llm.factory import build_llm_provider

logger = logging.getLogger(__name__)


async def _cmd_chat_start(bridge: HarnessBridge, params: dict) -> dict:
    return await bridge.run(lambda: handlers.chat_start(bridge.ctx))


async def _cmd_chat_send(bridge: HarnessBridge, params: dict) -> dict:
    return await bridge.run(lambda: handlers.chat_send(bridge.ctx, params["message"]))


async def _cmd_desires_list(bridge: HarnessBridge, params: dict) -> dict:
    return await bridge.run(lambda: handlers.desires_list(bridge.ctx, show_all=params.get("show_all", False)))


async def _cmd_desires_history(bridge: HarnessBridge, params: dict) -> dict:
    return await bridge.run(lambda: handlers.desires_history(bridge.ctx, desire_id=params["desire_id"]))


async def _cmd_actions_list(bridge: HarnessBridge, params: dict) -> dict:
    return await bridge.run(lambda: handlers.actions_list(bridge.ctx, limit=params.get("limit", 20)))


COMMAND_HANDLERS: dict[str, Callable[[HarnessBridge, dict], Awaitable[dict]]] = {
    "chat.start": _cmd_chat_start,
    "chat.send": _cmd_chat_send,
    "desires.list": _cmd_desires_list,
    "desires.history": _cmd_desires_history,
    "actions.list": _cmd_actions_list,
}


async def _dispatch(bridge: HarnessBridge, request: Request) -> Response:
    handler = COMMAND_HANDLERS.get(request.command)
    if handler is None:
        return Response(id=request.id, ok=False, error=f"Unknown command: {request.command}")
    try:
        result = await handler(bridge, request.params)
    except Exception as e:
        logger.exception("command %s failed", request.command)
        return Response(id=request.id, ok=False, error=str(e))
    return Response(id=request.id, ok=True, result=result)


async def _handle_connection(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, bridge: HarnessBridge
) -> None:
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                request = decode_request(line)
            except Exception:
                # Can't recover a request id to reply to, so the connection is closed
                # rather than silently dropping the line — leaving the caller's
                # blocking readline() waiting forever for a response that can't come.
                logger.exception("received malformed request line, closing connection")
                break
            response = await _dispatch(bridge, request)
            writer.write(encode(response))
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def _serve(paths: DaemonPaths, settings: Settings, *, stop_event: asyncio.Event | None = None) -> None:
    provider = build_llm_provider(settings)
    bridge = HarnessBridge(settings.db_path, provider)

    if paths.sock_path.exists():
        paths.sock_path.unlink()

    server = await asyncio.start_unix_server(
        lambda r, w: _handle_connection(r, w, bridge), path=str(paths.sock_path)
    )
    os.chmod(paths.sock_path, 0o600)  # defense in depth alongside the owner-only directory
    write_pid_file(paths.pid_path, pid=os.getpid(), sock_path=paths.sock_path)

    stop_event = stop_event or asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    try:
        async with server:
            await stop_event.wait()
    finally:
        bridge.close()
        if paths.sock_path.exists():
            paths.sock_path.unlink()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    paths = DaemonPaths.for_settings(settings)

    lock = DaemonLock(paths.lock_path)
    lock.acquire()
    try:
        asyncio.run(_serve(paths, settings))
    finally:
        lock.release()


if __name__ == "__main__":
    main()
