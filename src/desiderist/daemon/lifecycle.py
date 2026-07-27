import fcntl
import json
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from desiderist.config import Settings


@dataclass
class DaemonPaths:
    lock_path: Path
    pid_path: Path
    sock_path: Path
    log_path: Path

    @classmethod
    def for_settings(cls, settings: "Settings") -> "DaemonPaths":
        return cls.for_dir(settings.db_path.parent)

    @classmethod
    def for_dir(cls, directory: Path) -> "DaemonPaths":
        directory.mkdir(parents=True, exist_ok=True)
        # Owner-only: without traversal permission here, other local users can't
        # reach the control socket regardless of its own file mode.
        os.chmod(directory, 0o700)
        return cls(
            lock_path=directory / "daemon.lock",
            pid_path=directory / "daemon.pid",
            sock_path=directory / "daemon.sock",
            log_path=directory / "daemon.log",
        )


class AlreadyRunningError(RuntimeError):
    pass


class DaemonLock:
    """Holds an exclusive flock on lock_path for the daemon's whole lifetime. The lock
    (not the pid file) is the source of truth for whether a daemon is really running —
    it's released automatically by the OS even if the process is killed, sidestepping
    stale-pid/pid-reuse races a plain `os.kill(pid, 0)` check is prone to."""

    def __init__(self, lock_path: Path):
        self._lock_path = lock_path
        self._fh = None

    def acquire(self) -> None:
        self._fh = open(self._lock_path, "a")
        try:
            fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._fh.close()
            self._fh = None
            raise AlreadyRunningError(f"Another daemon already holds {self._lock_path}") from None

    def release(self) -> None:
        if self._fh is not None:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None


def is_running(lock_path: Path) -> bool:
    if not lock_path.exists():
        return False
    with open(lock_path, "a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fh, fcntl.LOCK_UN)
        return False


def write_pid_file(pid_path: Path, *, pid: int, sock_path: Path) -> None:
    pid_path.write_text(json.dumps({"pid": pid, "sock_path": str(sock_path), "started_at": time.time()}))


def read_pid_file(pid_path: Path) -> dict | None:
    if not pid_path.exists():
        return None
    try:
        return json.loads(pid_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def stop(paths: DaemonPaths, *, timeout: float = 5.0) -> bool:
    """Signal the running daemon to stop. Returns True once it's confirmed stopped."""
    if not is_running(paths.lock_path):
        return True

    info = read_pid_file(paths.pid_path)
    if info is None:
        return not is_running(paths.lock_path)

    try:
        os.kill(info["pid"], signal.SIGTERM)
    except ProcessLookupError:
        return True

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_running(paths.lock_path):
            return True
        time.sleep(0.1)

    try:
        os.kill(info["pid"], signal.SIGKILL)
    except ProcessLookupError:
        pass
    return not is_running(paths.lock_path)
