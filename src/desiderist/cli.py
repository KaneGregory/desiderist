import typer

from desiderist import __version__
from desiderist.config import load_settings
from desiderist.daemon.cli import daemon_app
from desiderist.daemon.client import DaemonClient, DaemonNotRunningError
from desiderist.daemon.lifecycle import DaemonPaths
from desiderist.llm.base import messages_from_turns

app = typer.Typer(add_completion=False)
app.add_typer(daemon_app, name="daemon")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"desiderist {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show the version and exit."
    ),
) -> None:
    pass


# Kept for backwards compatibility with tests exercising the plain conversion.
def turns_to_messages(turns: list[dict]):
    return messages_from_turns(turns)


def _connect_or_exit() -> DaemonClient:
    paths = DaemonPaths.for_settings(load_settings())
    try:
        return DaemonClient(paths.sock_path)
    except DaemonNotRunningError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None


@app.command()
def chat() -> None:
    """Interactive chat: each turn extracts/updates desires, plans, and executes actions."""
    settings = load_settings()
    typer.echo(f"desiderist chat (using {settings.resolved_provider}) — type 'exit' to quit")

    with _connect_or_exit() as client:
        start_result = client.call("chat.start")
        for message in start_result["messages"]:
            typer.echo(message)

        while True:
            try:
                user_input = typer.prompt(">")
            except (EOFError, typer.Abort):
                break
            if user_input.strip().lower() in {"exit", "quit"}:
                break

            try:
                result = client.call("chat.send", message=user_input)
            except RuntimeError as e:
                typer.echo(f"Error: {e}", err=True)
                continue
            for message in result["messages"]:
                typer.echo(message)


@app.command()
def desires(
    history: str | None = typer.Option(
        None, "--history", help="Show the event history for a single desire id."
    ),
    show_all: bool = typer.Option(
        False, "--all", "-a", help="Show all desires, including fulfilled/abandoned/superseded ones."
    ),
) -> None:
    """Inspect tracked desires — the extracted state, independent of the chat transcript."""
    with _connect_or_exit() as client:
        if history:
            events = client.call("desires.history", desire_id=history)["events"]
            if not events:
                typer.echo(f"No history for desire {history}")
                return
            for event in events:
                typer.echo(f"{event['created_at']}  {event['op']:<10}  {event['reasoning']}")
            return

        desire_list = client.call("desires.list", show_all=show_all)["desires"]
        if not desire_list:
            typer.echo("No desires tracked yet.")
            return

        typer.echo(f"{'id':<36}  {'status':<10}  {'pri':<3}  {'conf':<5}  {'updated_at':<26}  description")
        for d in desire_list:
            typer.echo(
                f"{d['id']:<36}  {d['status']:<10}  {d['priority']:<3}  {d['confidence']:<5}  "
                f"{d['updated_at']:<26}  {d['description']}"
            )


@app.command()
def actions(limit: int = typer.Option(20, "--limit", "-n", help="Number of recent action log entries to show.")) -> None:
    """Inspect the action log — what the harness actually did, and whether it succeeded."""
    with _connect_or_exit() as client:
        entries = client.call("actions.list", limit=limit)["entries"]
        if not entries:
            typer.echo("No actions logged yet.")
            return

        for entry in entries:
            status = "ok" if entry["success"] else "FAILED"
            typer.echo(f"{entry['created_at']}  {status:<6}  {entry['action_name']:<24}  {entry['params_json']}")


if __name__ == "__main__":
    app()
