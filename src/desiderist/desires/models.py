from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DesireStatus(str, Enum):
    ACTIVE = "active"
    FULFILLED = "fulfilled"
    ABANDONED = "abandoned"
    SUPERSEDED = "superseded"


class Desire(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str
    user_id: str
    description: str
    status: DesireStatus
    priority: int
    confidence: float
    created_at: datetime
    updated_at: datetime
    source_turn_id: str
    last_touched_turn_id: str
    supersedes_id: str | None = None


class DesireOp(BaseModel):
    op: Literal["create", "update", "fulfill", "abandon", "contradict"]
    desire_id: str | None = None
    description: str | None = None
    priority: int | None = None
    confidence: float | None = None
    reasoning: str


class ExtractionResult(BaseModel):
    ops: list[DesireOp]
