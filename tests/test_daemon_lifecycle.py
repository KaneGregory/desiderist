import subprocess
import sys
import time

from desiderist.daemon.lifecycle import (
    AlreadyRunningError,
    DaemonLock,
    DaemonPaths,
    is_running,
    read_pid_file,
    stop,
    write_pid_file,
)


def test_daemon_paths_creates_directory(tmp_path):
    directory = tmp_path / "nested"
    paths = DaemonPaths.for_dir(directory)
    assert directory.exists()
    assert paths.lock_path == directory / "daemon.lock"
    assert paths.sock_path == directory / "daemon.sock"


def test_lock_acquire_and_release(tmp_path):
    lock_path = tmp_path / "daemon.lock"
    assert is_running(lock_path) is False

    lock = DaemonLock(lock_path)
    lock.acquire()
    assert is_running(lock_path) is True

    lock.release()
    assert is_running(lock_path) is False


def test_lock_raises_when_already_held(tmp_path):
    lock_path = tmp_path / "daemon.lock"
    first = DaemonLock(lock_path)
    first.acquire()

    second = DaemonLock(lock_path)
    try:
        second.acquire()
        raise AssertionError("expected AlreadyRunningError")
    except AlreadyRunningError:
        pass

    first.release()


def test_pid_file_round_trip(tmp_path):
    pid_path = tmp_path / "daemon.pid"
    assert read_pid_file(pid_path) is None

    write_pid_file(pid_path, pid=1234, sock_path=tmp_path / "daemon.sock")
    info = read_pid_file(pid_path)
    assert info["pid"] == 1234
    assert info["sock_path"] == str(tmp_path / "daemon.sock")


def test_stop_terminates_a_running_process(tmp_path):
    paths = DaemonPaths.for_dir(tmp_path)
    script = (
        "import fcntl, os, json, time\n"
        f"fh = open({str(paths.lock_path)!r}, 'a')\n"
        "fcntl.flock(fh, fcntl.LOCK_EX)\n"
        f"open({str(paths.pid_path)!r}, 'w').write(json.dumps({{'pid': os.getpid(), 'sock_path': ''}}))\n"
        "time.sleep(30)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", script])
    try:
        deadline = time.monotonic() + 5.0
        while not is_running(paths.lock_path) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert is_running(paths.lock_path) is True

        assert stop(paths, timeout=5.0) is True
        assert is_running(paths.lock_path) is False
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
