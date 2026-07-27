import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, TypeVar

from desiderist.desires.store import DesireStore
from desiderist.llm.base import LLMProvider
from desiderist.persistence.db import connect
from desiderist.persistence.repositories import (
    ActionLogRepo,
    CapabilityRepo,
    ConversationRepo,
    DesireEventRepo,
    DesireRepo,
)

T = TypeVar("T")


class HarnessContext:
    def __init__(self, db_path: Path, provider: LLMProvider):
        conn = connect(db_path)
        self.conversations = ConversationRepo(conn)
        self.store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))
        self.action_log = ActionLogRepo(conn)
        self.capabilities = CapabilityRepo(conn)
        self.provider = provider


class HarnessBridge:
    """Owns the single worker thread all harness/DB code runs on, so the sqlite3
    connection (default check_same_thread=True) is only ever touched from one thread,
    and exposes `run` to hop onto it from the asyncio loop thread."""

    def __init__(self, db_path: Path, provider: LLMProvider):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="harness")
        self.ctx = self._executor.submit(HarnessContext, db_path, provider).result()

    async def run(self, fn: Callable[[], T]) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn)

    def close(self) -> None:
        self._executor.shutdown(wait=True)
