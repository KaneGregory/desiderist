import socket
import uuid
from pathlib import Path

from desiderist.daemon.protocol import Request, decode_response, encode


class DaemonNotRunningError(RuntimeError):
    pass


class DaemonClient:
    def __init__(self, sock_path: Path):
        try:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.connect(str(sock_path))
        except (FileNotFoundError, ConnectionRefusedError) as e:
            raise DaemonNotRunningError(
                f"Could not connect to the daemon at {sock_path} — is it running? "
                "Try `desiderist daemon start`."
            ) from e
        self._fh = self._sock.makefile("rwb")

    def call(self, command: str, **params) -> dict | list:
        request = Request(id=str(uuid.uuid4()), command=command, params=params)
        self._fh.write(encode(request))
        self._fh.flush()
        line = self._fh.readline()
        if not line:
            raise DaemonNotRunningError("Daemon closed the connection unexpectedly.")
        response = decode_response(line)
        if not response.ok:
            raise RuntimeError(response.error or "Unknown daemon error")
        return response.result

    def close(self) -> None:
        self._fh.close()
        self._sock.close()

    def __enter__(self) -> "DaemonClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
