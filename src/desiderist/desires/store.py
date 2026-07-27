from datetime import datetime, timezone

from desiderist.desires.models import Desire, DesireOp, DesireStatus
from desiderist.persistence.repositories import DesireEventRepo, DesireRepo, new_id

DEFAULT_PRIORITY = 3
DEFAULT_CONFIDENCE = 0.7

ONBOARDING_DESIRE_DESCRIPTION = "I want Desiderist to identify my initial desires"
ONBOARDING_SEED_REASONING = "System-seeded onboarding desire for a new user — not extracted from user input."


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_desire(row: dict) -> Desire:
    return Desire.model_validate(row)


def _desire_to_row(desire: Desire) -> dict:
    row = desire.model_dump(mode="json")
    return row


def _new_desire(
    *,
    now: str,
    user_id: str,
    description: str,
    priority: int,
    confidence: float,
    source_turn_id: str | None,
    last_touched_turn_id: str | None,
    supersedes_id: str | None = None,
) -> Desire:
    return Desire(
        id=new_id(),
        user_id=user_id,
        description=description,
        status=DesireStatus.ACTIVE,
        priority=priority,
        confidence=confidence,
        created_at=now,
        updated_at=now,
        source_turn_id=source_turn_id,
        last_touched_turn_id=last_touched_turn_id,
        supersedes_id=supersedes_id,
    )


class DesireStore:
    def __init__(self, desire_repo: DesireRepo, event_repo: DesireEventRepo):
        self._desires = desire_repo
        self._events = event_repo

    def apply_ops(self, ops: list[DesireOp], *, turn_id: str, raw_llm_response: str, user_id: str = "local-user") -> None:
        for op in ops:
            desire_id = self._apply_op(op, turn_id=turn_id, user_id=user_id)
            self._events.add_event(
                desire_id=desire_id,
                op=op.op,
                reasoning=op.reasoning,
                diff=op.model_dump(exclude={"reasoning"}),
                raw_llm_response=raw_llm_response,
                turn_id=turn_id,
            )

    def _apply_op(self, op: DesireOp, *, turn_id: str, user_id: str) -> str:
        now = _now_iso()

        if op.op == "create":
            desire = _new_desire(
                now=now,
                user_id=user_id,
                description=op.description,
                priority=op.priority or DEFAULT_PRIORITY,
                confidence=op.confidence if op.confidence is not None else DEFAULT_CONFIDENCE,
                source_turn_id=turn_id,
                last_touched_turn_id=turn_id,
            )
            self._desires.upsert(_desire_to_row(desire))
            return desire.id

        existing = _row_to_desire(self._desires.get(op.desire_id))

        if op.op == "update":
            existing.description = op.description or existing.description
            existing.priority = op.priority if op.priority is not None else existing.priority
            existing.confidence = op.confidence if op.confidence is not None else existing.confidence
            existing.updated_at = now
            existing.last_touched_turn_id = turn_id
            self._desires.upsert(_desire_to_row(existing))
            return existing.id

        if op.op == "fulfill":
            existing.status = DesireStatus.FULFILLED
            existing.updated_at = now
            existing.last_touched_turn_id = turn_id
            self._desires.upsert(_desire_to_row(existing))
            return existing.id

        if op.op == "abandon":
            existing.status = DesireStatus.ABANDONED
            existing.updated_at = now
            existing.last_touched_turn_id = turn_id
            self._desires.upsert(_desire_to_row(existing))
            return existing.id

        if op.op == "contradict":
            existing.status = DesireStatus.SUPERSEDED
            existing.updated_at = now
            existing.last_touched_turn_id = turn_id
            self._desires.upsert(_desire_to_row(existing))

            new_desire = _new_desire(
                now=now,
                user_id=user_id,
                description=op.description,
                priority=op.priority or DEFAULT_PRIORITY,
                confidence=op.confidence if op.confidence is not None else DEFAULT_CONFIDENCE,
                source_turn_id=turn_id,
                last_touched_turn_id=turn_id,
                supersedes_id=existing.id,
            )
            self._desires.upsert(_desire_to_row(new_desire))
            return new_desire.id

        raise ValueError(f"Unknown op: {op.op}")

    def seed_onboarding_desire(self, *, user_id: str = "local-user") -> Desire | None:
        if self.all(user_id):
            return None

        desire = _new_desire(
            now=_now_iso(),
            user_id=user_id,
            description=ONBOARDING_DESIRE_DESCRIPTION,
            priority=DEFAULT_PRIORITY,
            confidence=1.0,
            source_turn_id=None,
            last_touched_turn_id=None,
        )
        self._desires.upsert(_desire_to_row(desire))
        self._events.add_event(
            desire_id=desire.id,
            op="create",
            reasoning=ONBOARDING_SEED_REASONING,
            diff={"description": desire.description},
            raw_llm_response="",
            turn_id=None,
        )
        return desire

    def active(self, user_id: str = "local-user") -> list[Desire]:
        return [_row_to_desire(row) for row in self._desires.list_active(user_id)]

    def all(self, user_id: str = "local-user") -> list[Desire]:
        return [_row_to_desire(row) for row in self._desires.list_all(user_id)]

    def history(self, desire_id: str) -> list[dict]:
        return self._events.history(desire_id)
