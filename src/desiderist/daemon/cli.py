import shlex
import subprocess
import sys
import time

import typer

from desiderist.config import load_settings
from desiderist.daemon.client import DaemonClient, DaemonNotRunningError
from desiderist.daemon.lifecycle import DaemonPaths, is_running, read_pid_file
from desiderist.daemon.lifecycle import stop as stop_daemon

daemon_app = typer.Typer(help="Manage the Desiderist background daemon.")
capabilities_app = typer.Typer(help="Manage capability providers (MCP-backed action sources).")


def _paths() -> DaemonPaths:
    return DaemonPaths.for_settings(load_settings())


def _client() -> DaemonClient:
    try:
        return DaemonClient(_paths().sock_path)
    except DaemonNotRunningError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None


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


@capabilities_app.command("register")
def capabilities_register(
    name: str,
    stdio: str = typer.Option(
        ..., "--stdio", help='Command to launch the provider\'s MCP server, e.g. "python server.py".'
    ),
    description: str = typer.Option(..., "--description", help="What this provider is/does."),
) -> None:
    """Register a new capability provider. This only records it as pending —
    Desiderist does not connect to it (or run the command at all) until you `approve`
    it."""
    try:
        parts = shlex.split(stdio)
    except ValueError as e:
        typer.echo(f"Invalid --stdio command: {e}", err=True)
        raise typer.Exit(code=1) from None
    if not parts:
        typer.echo("Invalid --stdio command: empty.", err=True)
        raise typer.Exit(code=1)

    transport = {"kind": "stdio", "command": parts[0], "args": parts[1:]}
    with _client() as client:
        result = client.call("capabilities.register", name=name, description=description, transport=transport)
        provider = result["provider"]
        typer.echo(f"Registered {provider['id']} ({provider['name']}) — pending approval.")


@capabilities_app.command("list")
def capabilities_list() -> None:
    """List registered capability providers."""
    with _client() as client:
        providers = client.call("capabilities.list")["providers"]
        if not providers:
            typer.echo("No capability providers registered.")
            return
        typer.echo(f"{'id':<36}  {'status':<10}  name")
        for p in providers:
            typer.echo(f"{p['id']:<36}  {p['status']:<10}  {p['name']}")


@capabilities_app.command("approve")
def capabilities_approve(provider_id: str) -> None:
    """Connect to a pending provider and pull in its tools."""
    with _client() as client:
        try:
            result = client.call("capabilities.approve", provider_id=provider_id)
        except RuntimeError as e:
            typer.echo(f"Approval failed: {e}", err=True)
            raise typer.Exit(code=1) from None
        typer.echo(f"Approved {result['provider']['name']}.")


@capabilities_app.command("revoke")
def capabilities_revoke(provider_id: str) -> None:
    """Disconnect and revoke a provider."""
    with _client() as client:
        try:
            result = client.call("capabilities.revoke", provider_id=provider_id)
        except RuntimeError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(code=1) from None
        typer.echo(f"Revoked {result['provider']['name']}.")


@capabilities_app.command("show")
def capabilities_show(provider_id: str) -> None:
    """Show a provider's details and discovered tools."""
    with _client() as client:
        try:
            detail = client.call("capabilities.show", provider_id=provider_id)
        except RuntimeError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(code=1) from None

        provider = detail["provider"]
        typer.echo(f"{provider['name']} ({provider['id']}) — {provider['status']}")
        typer.echo(provider["description"])
        if not detail["tools"]:
            typer.echo("No tools discovered yet.")
            return
        for tool in detail["tools"]:
            typer.echo(f"  - {tool['tool_name']}: {tool['description']}")
