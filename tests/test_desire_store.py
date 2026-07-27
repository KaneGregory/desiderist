from desiderist.desires.extraction import extract_desire_ops
from desiderist.desires.models import DesireStatus, ExtractionResult
from desiderist.desires.store import DesireStore
from desiderist.llm.fake import FakeLLMProvider
from desiderist.persistence.db import connect
from desiderist.persistence.repositories import ConversationRepo, DesireEventRepo, DesireRepo


def make_store():
    conn = connect(":memory:")
    conversations = ConversationRepo(conn)
    store = DesireStore(DesireRepo(conn), DesireEventRepo(conn))
    return conversations, store


def run_extraction(provider, store, conversations, message: str, active=None):
    turn = conversations.add_turn(role="user", content=message)
    result = extract_desire_ops(
        provider, active_desires=active or [], recent_turns=[], new_message=message
    )
    store.apply_ops(result.ops, turn_id=turn["id"], raw_llm_response="{}")
    return turn


def test_create_op_adds_active_desire():
    conversations, store = make_store()
    provider = FakeLLMProvider(
        extraction_responses=[
            ExtractionResult(
                ops=[{"op": "create", "description": "wants coffee", "reasoning": "user asked for coffee"}]
            )
        ]
    )

    run_extraction(provider, store, conversations, "I'd like a coffee")

    active = store.active()
    assert len(active) == 1
    assert active[0].description == "wants coffee"
    assert active[0].status == DesireStatus.ACTIVE
    assert len(store.history(active[0].id)) == 1


def test_update_op_changes_description_and_priority():
    conversations, store = make_store()
    create_provider = FakeLLMProvider(
        extraction_responses=[
            ExtractionResult(ops=[{"op": "create", "description": "wants coffee", "reasoning": "r"}])
        ]
    )
    run_extraction(create_provider, store, conversations, "I'd like a coffee")
    desire_id = store.active()[0].id

    update_provider = FakeLLMProvider(
        extraction_responses=[
            ExtractionResult(
                ops=[
                    {
                        "op": "update",
                        "desire_id": desire_id,
                        "description": "wants a large coffee",
                        "priority": 5,
                        "reasoning": "user specified size",
                    }
                ]
            )
        ]
    )
    run_extraction(update_provider, store, conversations, "actually make it large", active=store.active())

    active = store.active()
    assert len(active) == 1
    assert active[0].description == "wants a large coffee"
    assert active[0].priority == 5
    assert len(store.history(desire_id)) == 2


def test_fulfill_op_marks_desire_fulfilled():
    conversations, store = make_store()
    create_provider = FakeLLMProvider(
        extraction_responses=[
            ExtractionResult(ops=[{"op": "create", "description": "wants coffee", "reasoning": "r"}])
        ]
    )
    run_extraction(create_provider, store, conversations, "I'd like a coffee")
    desire_id = store.active()[0].id

    fulfill_provider = FakeLLMProvider(
        extraction_responses=[
            ExtractionResult(
                ops=[{"op": "fulfill", "desire_id": desire_id, "reasoning": "user got their coffee"}]
            )
        ]
    )
    run_extraction(fulfill_provider, store, conversations, "got it, thanks", active=store.active())

    assert store.active() == []
    all_desires = store.all()
    assert len(all_desires) == 1
    assert all_desires[0].status == DesireStatus.FULFILLED


def test_seed_onboarding_desire_creates_desire_for_empty_store():
    conversations, store = make_store()

    desire = store.seed_onboarding_desire()

    assert desire is not None
    assert desire.description == "I want Desiderist to identify my initial desires"
    assert desire.status == DesireStatus.ACTIVE
    assert desire.confidence == 1.0
    assert desire.source_turn_id is None
    assert desire.last_touched_turn_id is None

    active = store.active()
    assert len(active) == 1
    assert active[0].id == desire.id
    assert len(store.history(desire.id)) == 1


def test_seed_onboarding_desire_is_noop_for_existing_user():
    conversations, store = make_store()
    provider = FakeLLMProvider(
        extraction_responses=[
            ExtractionResult(ops=[{"op": "create", "description": "wants coffee", "reasoning": "r"}])
        ]
    )
    run_extraction(provider, store, conversations, "I'd like a coffee")

    desire = store.seed_onboarding_desire()

    assert desire is None
    all_desires = store.all()
    assert len(all_desires) == 1
    assert all_desires[0].description == "wants coffee"


def test_contradict_op_supersedes_and_creates_new_desire():
    conversations, store = make_store()
    create_provider = FakeLLMProvider(
        extraction_responses=[
            ExtractionResult(ops=[{"op": "create", "description": "wants coffee", "reasoning": "r"}])
        ]
    )
    run_extraction(create_provider, store, conversations, "I'd like a coffee")
    old_id = store.active()[0].id

    contradict_provider = FakeLLMProvider(
        extraction_responses=[
            ExtractionResult(
                ops=[
                    {
                        "op": "contradict",
                        "desire_id": old_id,
                        "description": "wants tea instead",
                        "reasoning": "user changed their mind",
                    }
                ]
            )
        ]
    )
    run_extraction(contradict_provider, store, conversations, "actually, tea instead", active=store.active())

    all_desires = store.all()
    assert len(all_desires) == 2
    old = next(d for d in all_desires if d.id == old_id)
    new = next(d for d in all_desires if d.id != old_id)
    assert old.status == DesireStatus.SUPERSEDED
    assert new.status == DesireStatus.ACTIVE
    assert new.description == "wants tea instead"
    assert new.supersedes_id == old_id
