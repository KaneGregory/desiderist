import json
import sqlite3
import uuid
from datetime import datetime, timezone


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def add_turn(self, role: str, content: str, user_id: str = "local-user") -> dict:
        turn = {
            "id": new_id(),
            "user_id": user_id,
            "role": role,
            "content": content,
            "created_at": now_iso(),
        }
        self._conn.execute(
            "INSERT INTO conversation_turns (id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (turn["id"], turn["user_id"], turn["role"], turn["content"], turn["created_at"]),
        )
        self._conn.commit()
        return turn

    def recent(self, limit: int = 20, user_id: str = "local-user") -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM conversation_turns WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


class DesireRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def upsert(self, desire: dict) -> None:
        self._conn.execute(
            """
            INSERT INTO desires (id, user_id, description, status, priority, confidence,
                                  created_at, updated_at, source_turn_id, last_touched_turn_id, supersedes_id)
            VALUES (:id, :user_id, :description, :status, :priority, :confidence,
                    :created_at, :updated_at, :source_turn_id, :last_touched_turn_id, :supersedes_id)
            ON CONFLICT(id) DO UPDATE SET
                description=excluded.description,
                status=excluded.status,
                priority=excluded.priority,
                confidence=excluded.confidence,
                updated_at=excluded.updated_at,
                last_touched_turn_id=excluded.last_touched_turn_id,
                supersedes_id=excluded.supersedes_id
            """,
            desire,
        )
        self._conn.commit()

    def get(self, desire_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM desires WHERE id = ?", (desire_id,)).fetchone()
        return dict(row) if row else None

    def list_active(self, user_id: str = "local-user") -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM desires WHERE user_id = ? AND status = 'active' ORDER BY priority DESC, updated_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_all(self, user_id: str = "local-user") -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM desires WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


class DesireEventRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def add_event(
        self, *, desire_id: str, op: str, reasoning: str, diff: dict, raw_llm_response: str, turn_id: str | None
    ) -> dict:
        event = {
            "id": new_id(),
            "desire_id": desire_id,
            "op": op,
            "reasoning": reasoning,
            "diff_json": json.dumps(diff),
            "raw_llm_response": raw_llm_response,
            "turn_id": turn_id,
            "created_at": now_iso(),
        }
        self._conn.execute(
            """INSERT INTO desire_events
               (id, desire_id, op, reasoning, diff_json, raw_llm_response, turn_id, created_at)
               VALUES (:id, :desire_id, :op, :reasoning, :diff_json, :raw_llm_response, :turn_id, :created_at)""",
            event,
        )
        self._conn.commit()
        return event

    def history(self, desire_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM desire_events WHERE desire_id = ? ORDER BY created_at ASC", (desire_id,)
        ).fetchall()
        return [dict(r) for r in rows]


class ActionLogRepo:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def add_entry(
        self,
        *,
        action_name: str,
        params: dict,
        result: dict,
        success: bool,
        turn_id: str | None,
        related_desire_ids: list[str] | None = None,
    ) -> dict:
        entry = {
            "id": new_id(),
            "action_name": action_name,
            "params_json": json.dumps(params),
            "result_json": json.dumps(result),
            "success": 1 if success else 0,
            "turn_id": turn_id,
            "related_desire_ids_json": json.dumps(related_desire_ids or []),
            "created_at": now_iso(),
        }
        self._conn.execute(
            """INSERT INTO action_log
               (id, action_name, params_json, result_json, success, turn_id, related_desire_ids_json, created_at)
               VALUES (:id, :action_name, :params_json, :result_json, :success, :turn_id,
                       :related_desire_ids_json, :created_at)""",
            entry,
        )
        self._conn.commit()
        return entry

    def recent(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM action_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
