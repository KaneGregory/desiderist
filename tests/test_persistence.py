from desiderist.persistence.db import connect
from desiderist.persistence.repositories import (
    ActionLogRepo,
    ConversationRepo,
    DesireEventRepo,
    DesireRepo,
)


def make_repos():
    conn = connect(":memory:")
    return conn, ConversationRepo(conn), DesireRepo(conn), DesireEventRepo(conn), ActionLogRepo(conn)


def test_conversation_repo_round_trip():
    _, conversations, *_ = make_repos()
    turn = conversations.add_turn(role="user", content="hello")
    assert turn["role"] == "user"
    assert turn["content"] == "hello"

    recent = conversations.recent()
    assert len(recent) == 1
    assert recent[0]["id"] == turn["id"]


def test_desire_repo_upsert_and_list_active():
    _, conversations, desires, *_ = make_repos()
    turn = conversations.add_turn(role="user", content="I want a coffee")

    desire = {
        "id": "d1",
        "user_id": "local-user",
        "description": "wants coffee",
        "status": "active",
        "priority": 3,
        "confidence": 0.9,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "source_turn_id": turn["id"],
        "last_touched_turn_id": turn["id"],
        "supersedes_id": None,
    }
    desires.upsert(desire)

    active = desires.list_active()
    assert len(active) == 1
    assert active[0]["description"] == "wants coffee"

    desire["status"] = "fulfilled"
    desires.upsert(desire)
    assert desires.list_active() == []
    assert desires.get("d1")["status"] == "fulfilled"


def test_desire_event_repo_history():
    _, conversations, _, events, _ = make_repos()
    turn = conversations.add_turn(role="user", content="I want a coffee")

    events.add_event(
        desire_id="d1",
        op="create",
        reasoning="user asked for coffee",
        diff={"description": "wants coffee"},
        raw_llm_response="{}",
        turn_id=turn["id"],
    )
    history = events.history("d1")
    assert len(history) == 1
    assert history[0]["op"] == "create"


def test_desire_repo_upsert_allows_null_turn_ids():
    _, _, desires, *_ = make_repos()

    desire = {
        "id": "d1",
        "user_id": "local-user",
        "description": "system-seeded desire",
        "status": "active",
        "priority": 3,
        "confidence": 1.0,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "source_turn_id": None,
        "last_touched_turn_id": None,
        "supersedes_id": None,
    }
    desires.upsert(desire)

    stored = desires.get("d1")
    assert stored["source_turn_id"] is None
    assert stored["last_touched_turn_id"] is None


def test_desire_event_repo_allows_null_turn_id():
    _, _, _, events, _ = make_repos()

    events.add_event(
        desire_id="d1",
        op="create",
        reasoning="system-seeded",
        diff={"description": "system-seeded desire"},
        raw_llm_response="",
        turn_id=None,
    )
    history = events.history("d1")
    assert len(history) == 1
    assert history[0]["turn_id"] is None


def test_action_log_repo_allows_null_turn_id():
    *_, action_log = make_repos()

    action_log.add_entry(
        action_name="communicate_with_user",
        params={"message": "hello"},
        result={},
        success=True,
        turn_id=None,
    )
    recent = action_log.recent()
    assert len(recent) == 1
    assert recent[0]["turn_id"] is None


def test_action_log_repo_records_and_lists():
    _, conversations, *_rest, action_log = make_repos()
    turn = conversations.add_turn(role="user", content="hi")

    action_log.add_entry(
        action_name="communicate_with_user",
        params={"message": "hello"},
        result={},
        success=True,
        turn_id=turn["id"],
    )
    recent = action_log.recent()
    assert len(recent) == 1
    assert recent[0]["action_name"] == "communicate_with_user"
    assert recent[0]["success"] == 1
