from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import api as backend_api
from backend.constants import AGENT_CONFIGS, MAX_EXCHANGES_PER_SHARK
from backend.services import livekit_service, shark_service, turn_service
from backend.utils.shark_utils import build_shark_instructions


class FakeRoomService:
    def __init__(self, existing_room_names=None):
        self._existing = set(existing_room_names or [])
        self.created_rooms = []

    async def list_rooms(self, req):
        names = list(getattr(req, "names", []))
        rooms = [SimpleNamespace(name=name) for name in names if name in self._existing]
        return SimpleNamespace(rooms=rooms)

    async def create_room(self, req):
        name = getattr(req, "name", None)
        self._existing.add(name)
        self.created_rooms.append(name)
        return SimpleNamespace(name=name)


class FakeLiveKitAPI:
    def __init__(self, *args, existing_room_names=None, **kwargs):
        self.room = FakeRoomService(existing_room_names=existing_room_names)

    async def aclose(self):
        return None


def _fake_turn_state(
    room_name, agent_names, entrepreneur_identity="founder-x", index=0
):
    return turn_service.SharkTurnState(
        connections={},
        turn_order=agent_names,
        current_turn_index=index,
        active_session=None,
        room_name=room_name,
        entrepreneur_identity=entrepreneur_identity,
    )


# ── /session-token ──────────────────────────────────────────────────────────


def test_token_with_agents_creates_room_and_connects_all(monkeypatch):
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")

    fake_lkapi = FakeLiveKitAPI()
    monkeypatch.setattr(
        "backend.controllers.session_controller.api.LiveKitAPI",
        lambda *a, **kw: fake_lkapi,
    )

    connected_calls = []

    async def fake_join(**kwargs):
        connected_calls.append(kwargs)
        turn_service.TURN_STATES[kwargs["room_name"]] = _fake_turn_state(
            kwargs["room_name"], kwargs["agent_names"], kwargs["entrepreneur_identity"]
        )
        return sorted(kwargs["agent_names"])

    monkeypatch.setattr(livekit_service, "join_agents_manually", fake_join)
    monkeypatch.setattr(
        "backend.controllers.session_controller.join_agents_manually", fake_join
    )

    client = TestClient(backend_api.app)
    resp = client.post(
        "/session-token",
        json={
            "participant_identity": "founder-1",
            "participant_name": "Founder",
            "room_config": {"name": "arena-1"},
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["server_url"] == "wss://example.livekit.cloud"
    assert data["room_name"] == "arena-1"
    assert data["room_created"] is True
    assert sorted(data["agents_requested"]) == ["Kevin", "Lori", "Mark"]
    assert sorted(data["agents_connected"]) == ["Kevin", "Lori", "Mark"]
    assert isinstance(data["participant_token"], str) and data["participant_token"]
    assert data["current_shark"] == "Mark"
    assert data["turn_order"] == ["Mark", "Kevin", "Lori"]

    assert fake_lkapi.room.created_rooms == ["arena-1"]
    assert len(connected_calls) == 1
    assert connected_calls[0]["room_name"] == "arena-1"
    assert connected_calls[0]["entrepreneur_identity"] == "founder-1"


def test_token_with_agents_is_idempotent_when_room_exists(monkeypatch):
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")

    fake_lkapi = FakeLiveKitAPI(existing_room_names={"arena-2"})
    monkeypatch.setattr(
        "backend.controllers.session_controller.api.LiveKitAPI",
        lambda *a, **kw: fake_lkapi,
    )

    async def fake_join(**kwargs):
        turn_service.TURN_STATES[kwargs["room_name"]] = _fake_turn_state(
            kwargs["room_name"], kwargs["agent_names"], kwargs["entrepreneur_identity"]
        )
        return sorted(kwargs["agent_names"])

    monkeypatch.setattr(livekit_service, "join_agents_manually", fake_join)
    monkeypatch.setattr(
        "backend.controllers.session_controller.join_agents_manually", fake_join
    )

    client = TestClient(backend_api.app)
    resp = client.post(
        "/session-token",
        json={"participant_identity": "founder-2", "room_name": "arena-2"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["room_name"] == "arena-2"
    assert data["room_created"] is False
    assert sorted(data["agents_connected"]) == ["Kevin", "Lori", "Mark"]
    assert fake_lkapi.room.created_rooms == []


def test_token_with_agents_requires_credentials(monkeypatch):
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)
    monkeypatch.delenv("LIVEKIT_URL", raising=False)

    client = TestClient(backend_api.app)
    resp = client.post(
        "/session-token",
        json={"participant_identity": "founder-3", "room_name": "arena-3"},
    )

    assert resp.status_code == 500
    assert resp.json()["detail"] == "LiveKit credentials not configured"


# ── SharkAgent turn counting ────────────────────────────────────────────────


def test_shark_agent_counts_user_messages_and_fires_handoff(monkeypatch):
    """SharkAgent fires on_turn_complete after MAX_EXCHANGES_PER_SHARK user messages."""
    import asyncio

    handoff_called = []

    async def fake_handoff():
        handoff_called.append(True)

    # Patch generate_reply so on_enter / _do_handoff don't actually call the LLM
    class FakeSession:
        def on(self, *a, **kw):
            pass

        def off(self, *a, **kw):
            pass

        async def generate_reply(self, **kwargs):
            pass

    agent = shark_service.SharkAgent("Mark", "instructions", fake_handoff)
    # Inject a fake session so on_enter / _on_conversation_item work without real infra
    agent._session = FakeSession()

    # Simulate user messages via _on_conversation_item
    class FakeItem:
        role = "user"

    class FakeEv:
        item = FakeItem()

    original_max = MAX_EXCHANGES_PER_SHARK

    async def run():
        # Trigger one fewer than the limit — should NOT fire handoff
        for _ in range(original_max - 1):
            agent._on_conversation_item(FakeEv())
        assert not handoff_called, "handoff fired too early"

        # Trigger the final message — should create the handoff task
        agent._on_conversation_item(FakeEv())
        # Give the event loop a tick to schedule the task
        await asyncio.sleep(0)

    asyncio.run(run())
    assert agent._handoff_triggered


def test_shark_agent_ignores_assistant_messages(monkeypatch):
    """SharkAgent should NOT count assistant (shark) messages toward the limit."""

    handoff_called = []

    async def fake_handoff():
        handoff_called.append(True)

    agent = shark_service.SharkAgent("Kevin", "instructions", fake_handoff)

    class FakeAssistantEv:
        class item:
            role = "assistant"

    for _ in range(MAX_EXCHANGES_PER_SHARK + 5):
        agent._on_conversation_item(FakeAssistantEv())

    assert not handoff_called
    assert agent._user_msg_count == 0


def test_shark_agent_handoff_does_not_tell_user_it_is_passing_to_next_shark(
    monkeypatch,
):
    import asyncio

    prompts = []

    class FakeSession:
        async def generate_reply(self, **kwargs):
            prompts.append(kwargs.get("instructions", ""))

    async def fake_handoff():
        return None

    state = turn_service.SharkTurnState(
        connections={},
        turn_order=["Mark", "Kevin", "Lori"],
        current_turn_index=0,
        active_session=None,
        room_name="arena-handoff",
        entrepreneur_identity="founder-z",
    )
    agent = shark_service.SharkAgent(
        "Mark", "instructions", fake_handoff, turn_state=state, chat_ctx=None
    )
    monkeypatch.setattr(
        agent,
        "_get_activity_or_raise",
        lambda: SimpleNamespace(session=FakeSession()),
    )

    asyncio.run(agent._do_handoff())

    assert prompts, "Expected a handoff prompt to be generated"
    handoff_prompt = prompts[-1]
    assert "passing" not in handoff_prompt.lower()
    assert "fellow shark" not in handoff_prompt.lower()


def test_build_shark_instructions_include_decision_and_collaboration_guidance():
    config = AGENT_CONFIGS["Mark"]
    state = turn_service.SharkTurnState(
        connections={},
        turn_order=["Mark", "Kevin", "Lori"],
        current_turn_index=0,
        active_session=None,
        room_name="arena-instructions",
        entrepreneur_identity="founder-a",
    )

    built = build_shark_instructions(config, state)

    assert "collect all the information" in built.lower()
    assert "final decision" in built.lower()
    assert "combined offer" in built.lower()


# ── /advance-turn (manual override) ────────────────────────────────────────


def test_advance_turn_cycles_to_next_shark(monkeypatch):
    close_called = []

    class FakeSession:
        async def aclose(self):
            close_called.append(True)

    room_name = "arena-turn"
    kevin_conn = livekit_service.SharkRoomConnection(
        room=None,
        agent_name="Kevin",
        config=AGENT_CONFIGS["Kevin"],
    )
    state = turn_service.SharkTurnState(
        connections={"Mark": None, "Kevin": kevin_conn, "Lori": None},
        turn_order=["Mark", "Kevin", "Lori"],
        current_turn_index=0,
        active_session=FakeSession(),
        room_name=room_name,
        entrepreneur_identity="founder-x",
    )
    turn_service.TURN_STATES[room_name] = state

    started = []

    async def fake_start(connection, google_api_key, entrepreneur_identity, turn_state):
        started.append(connection.agent_name)
        return FakeSession()

    async def fake_advance(s):
        # Simplified version of advance_turn_for_room for test isolation
        async with s.advance_lock:
            await s.active_session.aclose()
            s.active_session = None
            s.current_turn_index = (s.current_turn_index + 1) % len(s.turn_order)
            next_conn = s.connections[s.current_shark]
            s.active_session = await fake_start(
                next_conn, "key", s.entrepreneur_identity, s
            )

    monkeypatch.setattr(turn_service, "advance_turn_for_room", fake_advance)
    monkeypatch.setattr(
        "backend.controllers.turn_controller.advance_turn_for_room", fake_advance
    )
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

    client = TestClient(backend_api.app)
    resp = client.post("/advance-turn", json={"room_name": room_name})

    assert resp.status_code == 200
    data = resp.json()
    assert data["current_shark"] == "Kevin"
    assert data["current_index"] == 1
    assert close_called
    assert started == ["Kevin"]


def test_advance_turn_wraps_to_first_shark(monkeypatch):
    close_called = []

    class FakeSession:
        async def aclose(self):
            close_called.append(True)

    room_name = "arena-wrap"
    mark_conn = livekit_service.SharkRoomConnection(
        room=None, agent_name="Mark", config=AGENT_CONFIGS["Mark"]
    )
    state = turn_service.SharkTurnState(
        connections={"Mark": mark_conn, "Kevin": None, "Lori": None},
        turn_order=["Mark", "Kevin", "Lori"],
        current_turn_index=2,
        active_session=FakeSession(),
        room_name=room_name,
        entrepreneur_identity="founder-wrap",
    )
    turn_service.TURN_STATES[room_name] = state

    async def fake_advance(s):
        async with s.advance_lock:
            await s.active_session.aclose()
            s.active_session = None
            s.current_turn_index = (s.current_turn_index + 1) % len(s.turn_order)
            s.active_session = FakeSession()

    monkeypatch.setattr(turn_service, "advance_turn_for_room", fake_advance)
    monkeypatch.setattr(
        "backend.controllers.turn_controller.advance_turn_for_room", fake_advance
    )
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

    client = TestClient(backend_api.app)
    resp = client.post("/advance-turn", json={"room_name": room_name})

    assert resp.status_code == 200
    assert resp.json()["current_shark"] == "Mark"
    assert resp.json()["current_index"] == 0


def test_advance_turn_404_for_unknown_room():
    client = TestClient(backend_api.app)
    resp = client.post("/advance-turn", json={"room_name": "no-such-room-xyz"})
    assert resp.status_code == 404


# ── /turn-status ─────────────────────────────────────────────────────────────


def test_turn_status_returns_current_state():
    room_name = "arena-status"
    state = turn_service.SharkTurnState(
        connections={},
        turn_order=["Mark", "Kevin", "Lori"],
        current_turn_index=1,
        active_session=object(),
        room_name=room_name,
        entrepreneur_identity="founder-y",
    )
    turn_service.TURN_STATES[room_name] = state

    client = TestClient(backend_api.app)
    resp = client.get(f"/turn-status?room_name={room_name}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["current_shark"] == "Kevin"
    assert data["current_index"] == 1
    assert data["session_active"] is True


def test_turn_status_404_for_unknown_room():
    client = TestClient(backend_api.app)
    resp = client.get("/turn-status?room_name=no-such-room-xyz")
    assert resp.status_code == 404
