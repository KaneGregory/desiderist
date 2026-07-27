import subprocess
import sys
import time

import typer

from desiderist.config import load_settings
from desiderist.daemon.lifecycle import DaemonPaths, is_running, read_pid_file
from desiderist.daemon.lifecycle import stop as stop_daemon

daemon_app = typer.Typer(help="Manage the Desiderist background daemon.")


def _paths() -> DaemonPaths:
    return DaemonPaths.for_settings(load_settings())


@daemon_app.command()
def start(
    foreground: bool = typer.Option(
        False, "--foreground", help="Run in the foreground instead of backgrounding."
    ),
) -> None:
    """Start the daemon."""
    paths = _paths()
    if is_running(paths.lock_path):
        typer.echo("Daemon is already running.")
        return

    if foreground:
        from desiderist.daemon.server import main as server_main

        server_main()
        return

    log_fh = open(paths.log_path, "a")
    subprocess.Popen(
        [sys.executable, "-m", "desiderist.daemon.server"],
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if is_running(paths.lock_path):
            typer.echo(f"Daemon started (socket: {paths.sock_path}).")
            return
        time.sleep(0.1)
    typer.echo(f"Daemon did not start within 5s — check the log at {paths.log_path}", err=True)
    raise typer.Exit(code=1)


@daemon_app.command()
def stop() -> None:
    """Stop the daemon."""
    paths = _paths()
    if not is_running(paths.lock_path):
        typer.echo("Daemon is not running.")
        return
    if stop_daemon(paths):
        typer.echo("Daemon stopped.")
    else:
        typer.echo("Daemon did not stop cleanly (had to force-kill).", err=True)


@daemon_app.command()
def status() -> None:
    """Show whether the daemon is running."""
    paths = _paths()
    if not is_running(paths.lock_path):
        typer.echo("Daemon is not running.")
        return
    info = read_pid_file(paths.pid_path)
    if info:
        typer.echo(f"Daemon is running (pid={info['pid']}, socket={info['sock_path']}).")
    else:
        typer.echo("Daemon is running.")
