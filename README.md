# desiderist
An LLM harness that plans actions based off of user desires

This is milestone 1: a single-user loop. You chat freely; the harness extracts and
tracks your "desires" (goals/wants) from the conversation, plans actions to fulfill
them, and executes those actions — starting with the one built-in action, replying to
you. Everything is stored locally in SQLite.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

The LLM backend is pluggable. Desiderist picks one automatically:

- **Claude (Anthropic API)** — used if `ANTHROPIC_API_KEY` is set.
- **Local model (Ollama)** — used otherwise. Requires [Ollama](https://ollama.com) running
  locally with a model pulled:

  ```bash
  brew install ollama
  brew services start ollama
  ollama pull qwen2.5:14b-instruct
  ```

  Override the host or model with `DESIDERIST_OLLAMA_HOST`, `DESIDERIST_OLLAMA_CHAT_MODEL`,
  `DESIDERIST_OLLAMA_EXTRACTION_MODEL`, `DESIDERIST_OLLAMA_PLANNING_MODEL`. `qwen2.5:7b-instruct`
  or `llama3.1:8b-instruct-q4_0` are lighter alternatives if 14B is slow on your hardware.

  Note: unlike Claude, Ollama can't force the model to call a tool every turn — if it just
  replies in plain text instead of invoking an action, the harness treats that reply as an
  implicit call to `communicate_with_user` so every turn still produces a logged action.

Force a specific backend regardless of what's set with `DESIDERIST_LLM_PROVIDER=claude` or
`DESIDERIST_LLM_PROVIDER=ollama`.

## Usage

A background daemon owns the database and the harness loop; `chat`/`desires`/`actions` are
thin clients that talk to it over a local Unix socket. Start it first:

```bash
desiderist daemon start   # starts in the background
desiderist daemon status  # check whether it's running
desiderist daemon stop    # stop it
```

Use `desiderist daemon start --foreground` to run it attached to your terminal (useful for
development — logs go straight to stdout instead of `~/.desiderist/daemon.log`).

```bash
desiderist chat      # interactive chat loop — type 'exit' to quit
desiderist desires    # inspect currently tracked desires
desiderist desires --all              # include fulfilled/abandoned/superseded desires
desiderist desires --history <id>     # full audit trail for one desire
desiderist actions    # inspect the action log — what the harness actually did
```

By default, state is stored in `~/.desiderist/desiderist.db`, alongside the daemon's lock,
pid, socket, and log files. Override the database location with `DESIDERIST_DB_PATH` (the
daemon's other files follow it, living in the same directory). Claude models used for
chat/extraction/planning can be overridden with `DESIDERIST_CHAT_MODEL`,
`DESIDERIST_EXTRACTION_MODEL`, and `DESIDERIST_PLANNING_MODEL`.

## Development

```bash
.venv/bin/pytest
```
