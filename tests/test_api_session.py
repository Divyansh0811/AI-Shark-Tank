from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import api as backend_api
from backend.app.routers import session as session_router
from backend.app.services import agents as agent_service
from backend.app.services.event_bus import EventBus
from backend.app.state import RoomTurnState


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


def test_token_with_agents_creates_room_and_connects_all(monkeypatch):
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")

    fake_lkapi = FakeLiveKitAPI()
    monkeypatch.setattr(
        session_router.lk_api,
        "LiveKitAPI",
        lambda *args, **kwargs: fake_lkapi,
    )

    connected_calls = []

    async def fake_join_agents_manually(**kwargs):
        connected_calls.append(kwargs)
        return sorted(kwargs["agent_names"])

    monkeypatch.setattr(
        session_router,
        "join_agents_manually",
        fake_join_agents_manually,
    )

    client = TestClient(backend_api.app)
    response = client.post(
        "/session-token",
        json={
            "participant_identity": "founder-1",
            "participant_name": "Founder",
            "room_config": {"name": "arena-1"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["server_url"] == "wss://example.livekit.cloud"
    assert data["room_name"] == "arena-1"
    assert data["room_created"] is True
    assert sorted(data["agents_requested"]) == ["Kevin", "Lori", "Mark"]
    assert sorted(data["agents_connected"]) == ["Kevin", "Lori", "Mark"]
    assert isinstance(data["participant_token"], str)
    assert data["participant_token"]

    assert fake_lkapi.room.created_rooms == ["arena-1"]
    assert len(connected_calls) == 1
    assert connected_calls[0]["room_name"] == "arena-1"
    assert connected_calls[0]["founder_identity"] == "founder-1"


def test_token_with_agents_is_idempotent_when_room_exists(monkeypatch):
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")

    fake_lkapi = FakeLiveKitAPI(existing_room_names={"arena-2"})
    monkeypatch.setattr(
        session_router.lk_api,
        "LiveKitAPI",
        lambda *args, **kwargs: fake_lkapi,
    )

    async def fake_join_agents_manually(**kwargs):
        return sorted(kwargs["agent_names"])

    monkeypatch.setattr(
        session_router,
        "join_agents_manually",
        fake_join_agents_manually,
    )

    client = TestClient(backend_api.app)
    response = client.post(
        "/session-token",
        json={
            "participant_identity": "founder-2",
            "participant_name": "Founder",
            "room_name": "arena-2",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["room_name"] == "arena-2"
    assert data["room_created"] is False
    assert sorted(data["agents_connected"]) == ["Kevin", "Lori", "Mark"]
    assert fake_lkapi.room.created_rooms == []


def test_token_with_agents_requires_credentials(monkeypatch):
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)
    monkeypatch.delenv("LIVEKIT_URL", raising=False)

    client = TestClient(backend_api.app)
    response = client.post(
        "/session-token",
        json={
            "participant_identity": "founder-3",
            "participant_name": "Founder",
            "room_name": "arena-3",
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "LiveKit credentials not configured"


class FakeAgentSession:
    def __init__(self):
        self.interrupt_calls = 0
        self.reply_calls = []

    async def interrupt(self, force: bool = False):
        self.interrupt_calls += 1

    def generate_reply(self, **kwargs):
        self.reply_calls.append(kwargs)


def test_handle_user_turn_round_robin_and_dedupe():
    state = RoomTurnState(
        agent_order=["Mark", "Kevin", "Lori"],
        founder_identity="founder",
        next_agent_idx=0,
        shared_context=[],
        last_handled_turn_key="",
        awaiting_reply_from=None,
        greeted=False,
        orchestrator_wired=True,
        event_bus=EventBus(),
        lock=agent_service.asyncio.Lock(),
    )

    mark = FakeAgentSession()
    kevin = FakeAgentSession()

    agent_service.asyncio.run(
        agent_service.handle_user_turn(
            room_name="arena",
            triggering_agent="Kevin",
            session=kevin,
            state=state,
            transcript="Hello sharks",
            speaker_id="founder",
        )
    )
    assert kevin.reply_calls == []
    assert kevin.interrupt_calls == 0

    agent_service.asyncio.run(
        agent_service.handle_user_turn(
            room_name="arena",
            triggering_agent="Mark",
            session=mark,
            state=state,
            transcript="Hello sharks",
            speaker_id="founder",
        )
    )
    assert len(mark.reply_calls) == 1
    assert mark.interrupt_calls == 0
    assert state.next_agent_idx == 0
    assert state.awaiting_reply_from == "Mark"

    agent_service.asyncio.run(
        agent_service.handle_user_turn(
            room_name="arena",
            triggering_agent="Kevin",
            session=kevin,
            state=state,
            transcript="Hello sharks",
            speaker_id="founder",
        )
    )
    assert kevin.reply_calls == []
    assert kevin.interrupt_calls == 0

    agent_service.asyncio.run(
        agent_service.handle_user_turn(
            room_name="arena",
            triggering_agent="Kevin",
            session=kevin,
            state=state,
            transcript="Our revenue is $2M ARR",
            speaker_id="founder",
        )
    )
    assert len(kevin.reply_calls) == 0

    state.next_agent_idx = 1
    agent_service.asyncio.run(
        agent_service.handle_user_turn(
            room_name="arena",
            triggering_agent="Kevin",
            session=kevin,
            state=state,
            transcript="Our revenue is $2M ARR",
            speaker_id="founder",
        )
    )
    assert len(kevin.reply_calls) == 1
    assert state.next_agent_idx == 1
    assert state.awaiting_reply_from == "Kevin"
