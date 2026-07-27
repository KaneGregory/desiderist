import anthropic
import httpx
import ollama
import typer

from desiderist import __version__
from desiderist.config import load_settings
from desiderist.desires.store import DesireStore
from desiderist.harness.loop import run_onboarding, run_turn
from desiderist.llm.base import messages_from_turns
from desiderist.llm.factory import build_llm_provider
from desiderist.persistence.db import connect
from desiderist.persistence.repositories import ActionLogRepo, ConversationRepo, DesireEventRepo, DesireRepo

app = typer.Typer(add_completion=False)


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


@app.command()
def chat() -> None:
    """Interactive chat: each turn extracts/updates desires, plans, and executes actions."""
    settings = load_settings()
    try:
        provider = build_llm_provider(settings)
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from None

    conn = connect(settings.db_path)
    conversations = ConversationRepo(conn)
    store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))
    action_log = ActionLogRepo(conn)

    typer.echo(f"desiderist chat (using {settings.resolved_provider}) — type 'exit' to quit")
    run_onboarding(store=store, conversations=conversations, action_log=action_log)

    while True:
        try:
            user_input = typer.prompt(">")
        except (EOFError, typer.Abort):
            break
        if user_input.strip().lower() in {"exit", "quit"}:
            break

        try:
            run_turn(
                provider=provider,
                store=store,
                conversations=conversations,
                action_log=action_log,
                user_message=user_input,
            )
        except anthropic.AuthenticationError:
            typer.echo("Authentication failed — check ANTHROPIC_API_KEY.", err=True)
            raise typer.Exit(code=1) from None
        except anthropic.RateLimitError as e:
            retry_after = e.response.headers.get("retry-after", "a bit")
            typer.echo(f"Rate limited — try again in {retry_after}s.", err=True)
        except anthropic.APIStatusError as e:
            typer.echo(f"API error ({e.status_code}): {e.message}", err=True)
        except anthropic.APIConnectionError:
            typer.echo("Network error talking to the Claude API — check your connection.", err=True)
        except ollama.ResponseError as e:
            typer.echo(f"Ollama error: {e.error}", err=True)
        except httpx.ConnectError:
            typer.echo(
                "Couldn't reach Ollama — is it running? Try `brew services start ollama`.", err=True
            )


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
    settings = load_settings()
    conn = connect(settings.db_path)
    store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))

    if history:
        events = store.history(history)
        if not events:
            typer.echo(f"No history for desire {history}")
            return
        for event in events:
            typer.echo(f"{event['created_at']}  {event['op']:<10}  {event['reasoning']}")
        return

    desire_list = store.all() if show_all else store.active()
    if not desire_list:
        typer.echo("No desires tracked yet.")
        return

    typer.echo(f"{'id':<36}  {'status':<10}  {'pri':<3}  {'conf':<5}  {'updated_at':<26}  description")
    for d in desire_list:
        typer.echo(
            f"{d.id:<36}  {d.status.value:<10}  {d.priority:<3}  {d.confidence:<5}  "
            f"{d.updated_at.isoformat():<26}  {d.description}"
        )


@app.command()
def actions(limit: int = typer.Option(20, "--limit", "-n", help="Number of recent action log entries to show.")) -> None:
    """Inspect the action log — what the harness actually did, and whether it succeeded."""
    settings = load_settings()
    conn = connect(settings.db_path)
    action_log = ActionLogRepo(conn)

    entries = action_log.recent(limit=limit)
    if not entries:
        typer.echo("No actions logged yet.")
        return

    for entry in entries:
        status = "ok" if entry["success"] else "FAILED"
        typer.echo(f"{entry['created_at']}  {status:<6}  {entry['action_name']:<24}  {entry['params_json']}")


if __name__ == "__main__":
    app()
