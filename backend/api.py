import asyncio
import os
from dataclasses import dataclass, field
from typing import Callable, Coroutine, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from livekit import api, rtc
from livekit.agents import Agent, AgentSession, room_io
from livekit.plugins import google
from livekit.protocol.room import RoomConfiguration
from pydantic import BaseModel

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# How many entrepreneur messages each shark gets before passing to the next
MAX_EXCHANGES_PER_SHARK = 3


class TokenRequest(BaseModel):
    room_name: Optional[str] = None
    participant_identity: Optional[str] = None
    participant_name: Optional[str] = None
    participant_metadata: Optional[str] = None
    participant_attributes: Optional[Dict[str, str]] = None
    room_config: Optional[dict] = None


class SessionTokenRequest(TokenRequest):
    agent_names: Optional[List[str]] = None


class AdvanceTurnRequest(BaseModel):
    room_name: str


DEFAULT_AGENT_NAMES = ["Mark", "Kevin", "Lori"]
AGENT_CONFIGS = {
    "Mark": {
        "voice": "Puck",
        "temperature": 0.6,
        "instructions": (
            "You are Mark Cuban from Shark Tank. You are bold, tech-focused, and "
            "look for scalability."
        ),
    },
    "Kevin": {
        "voice": "Puck",
        "temperature": 0.6,
        "instructions": (
            "You are Kevin O'Leary from Shark Tank. You are cynical, focused on "
            "royalties and margins."
        ),
    },
    "Lori": {
        "voice": "Kore",
        "temperature": 0.8,
        "instructions": (
            "You are Lori Greiner from Shark Tank. Queen of QVC. You look for hero "
            "products with mass-market appeal."
        ),
    },
}

AGENT_JOIN_LOCK = asyncio.Lock()


@dataclass
class SharkRoomConnection:
    """A persistent room connection for a single shark identity."""
    room: rtc.Room
    agent_name: str
    config: dict


@dataclass
class SharkTurnState:
    """All runtime state for a single pitch room."""
    connections: Dict[str, SharkRoomConnection]
    turn_order: List[str]
    current_turn_index: int
    active_session: Optional[AgentSession]
    room_name: str
    entrepreneur_identity: str
    advance_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def current_shark(self) -> str:
        return self.turn_order[self.current_turn_index]


TURN_STATES: Dict[str, SharkTurnState] = {}


class SharkAgent(Agent):
    """
    A shark that listens for MAX_EXCHANGES_PER_SHARK user messages then
    generates a farewell and hands off to the next shark automatically.
    """

    def __init__(
        self,
        name: str,
        instructions: str,
        on_turn_complete: Callable[[], Coroutine],
    ):
        super().__init__(instructions=instructions)
        self._name = name
        self._on_turn_complete = on_turn_complete
        self._user_msg_count = 0
        self._handoff_triggered = False

    async def on_enter(self) -> None:
        self.session.on("conversation_item_added", self._on_conversation_item)
        await self.session.generate_reply(
            instructions=(
                "Introduce yourself as this shark and ask the entrepreneur "
                "their first key business question."
            )
        )

    async def on_exit(self) -> None:
        self.session.off("conversation_item_added", self._on_conversation_item)

    def _on_conversation_item(self, ev) -> None:
        if self._handoff_triggered:
            return
        # Only count final user (entrepreneur) messages
        role = getattr(ev.item, "role", None)
        if role == "user":
            self._user_msg_count += 1
            print(
                f"[Turn] {self._name}: user message "
                f"{self._user_msg_count}/{MAX_EXCHANGES_PER_SHARK}"
            )
            if self._user_msg_count >= MAX_EXCHANGES_PER_SHARK:
                self._handoff_triggered = True
                asyncio.create_task(self._do_handoff())

    async def _do_handoff(self) -> None:
        """Generate a farewell, then signal the turn manager to advance."""
        print(f"[Turn] {self._name} wrapping up, handing off...")
        await self.session.generate_reply(
            instructions=(
                "Wrap up your questioning with one concise final thought. "
                "Tell the entrepreneur you're passing them to your fellow shark."
            )
        )
        await self._on_turn_complete()


def _get_livekit_credentials() -> Tuple[str, str, str]:
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    server_url = os.getenv("LIVEKIT_URL")
    if not all([api_key, api_secret, server_url]):
        raise HTTPException(
            status_code=500, detail="LiveKit credentials not configured"
        )
    return api_key, api_secret, server_url


def _normalize_ws_url(url: str) -> str:
    if url.startswith("https://"):
        return "wss://" + url[len("https://"):]
    if url.startswith("http://"):
        return "ws://" + url[len("http://"):]
    return url


def _resolve_room_name(request: TokenRequest) -> str:
    effective_room_name = request.room_name
    if (
        not effective_room_name
        and request.room_config
        and "name" in request.room_config
    ):
        effective_room_name = request.room_config["name"]
    if not effective_room_name:
        raise HTTPException(status_code=400, detail="room_name is required")
    return effective_room_name


def _build_participant_token(
    request: TokenRequest,
    *,
    api_key: str,
    api_secret: str,
    room_name: str,
) -> str:
    participant_identity = request.participant_identity
    if not participant_identity:
        raise HTTPException(status_code=400, detail="participant_identity is required")

    participant_name = request.participant_name or "anonymous"

    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity(participant_identity)
        .with_name(participant_name)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
    )

    if request.participant_metadata:
        token = token.with_metadata(request.participant_metadata)
    if request.participant_attributes:
        token = token.with_attributes(request.participant_attributes)
    if request.room_config:
        token = token.with_room_config(
            RoomConfiguration(
                name=request.room_config.get("name", room_name),
                empty_timeout=request.room_config.get("empty_timeout"),
            )
        )

    return token.to_jwt()


async def _ensure_room(lkapi: api.LiveKitAPI, room_name: str) -> bool:
    rooms_response = await lkapi.room.list_rooms(
        api.ListRoomsRequest(names=[room_name])
    )
    existing_rooms = getattr(rooms_response, "rooms", [])
    if existing_rooms:
        return False
    await lkapi.room.create_room(api.CreateRoomRequest(name=room_name))
    return True


def _build_agent_token(
    *,
    api_key: str,
    api_secret: str,
    room_name: str,
    agent_name: str,
) -> str:
    return (
        api.AccessToken(api_key, api_secret)
        .with_identity(f"agent-{agent_name.lower()}")
        .with_name(agent_name)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )


async def _start_shark_session(
    connection: SharkRoomConnection,
    google_api_key: str,
    entrepreneur_identity: str,
    turn_state: SharkTurnState,
) -> AgentSession:
    """Start an AgentSession for the given shark. Wires up the turn-complete callback."""
    config = connection.config

    async def on_turn_complete() -> None:
        await _advance_turn_for_room(turn_state)

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            api_key=google_api_key,
            voice=config["voice"],
            temperature=config["temperature"],
            instructions=config["instructions"],
        )
    )
    await session.start(
        room=connection.room,
        agent=SharkAgent(connection.agent_name, config["instructions"], on_turn_complete),
        room_options=room_io.RoomOptions(
            participant_identity=entrepreneur_identity,
            close_on_disconnect=False,
        ),
    )
    # Signal to the frontend that this shark is the active one
    await connection.room.local_participant.set_attributes({"shark.active": "true"})
    print(f"[Turn] Session started for {connection.agent_name}")
    return session


async def _advance_turn_for_room(state: SharkTurnState) -> None:
    """
    Close the current shark's session and start the next one.
    Protected by a per-room lock so concurrent calls are serialised.
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("[Turn] ERROR: GOOGLE_API_KEY missing, cannot advance turn")
        return

    async with state.advance_lock:
        # Mark current shark inactive in the room
        current_conn = state.connections.get(state.current_shark)
        if current_conn:
            try:
                await current_conn.room.local_participant.set_attributes(
                    {"shark.active": "false"}
                )
            except Exception as e:
                print(f"[Turn] Warning: could not clear shark.active for {state.current_shark}: {e}")

        # Close the outgoing session
        if state.active_session is not None:
            print(f"[Turn] Closing session for {state.current_shark}")
            await state.active_session.aclose()
            state.active_session = None

        # Advance turn index
        state.current_turn_index = (state.current_turn_index + 1) % len(state.turn_order)
        print(f"[Turn] It is now {state.current_shark}'s turn")

        # Start the new session
        next_conn = state.connections[state.current_shark]
        state.active_session = await _start_shark_session(
            next_conn, google_api_key, state.entrepreneur_identity, state
        )


async def _join_agents_manually(
    *,
    server_url: str,
    api_key: str,
    api_secret: str,
    room_name: str,
    agent_names: List[str],
    entrepreneur_identity: str,
) -> List[str]:
    """
    Connect all sharks to the room (for presence), then start only the first
    shark's AgentSession. Subsequent turns are triggered automatically by the
    conversation_item_added event inside SharkAgent.
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not configured")

    ws_url = _normalize_ws_url(server_url)

    async with AGENT_JOIN_LOCK:
        existing_state = TURN_STATES.get(room_name)
        if existing_state:
            all_connected = all(
                conn.room.isconnected()
                for conn in existing_state.connections.values()
            )
            if all_connected:
                return sorted(existing_state.connections.keys())

        # ── 1. Connect all sharks to the room for UI presence ──
        connections: Dict[str, SharkRoomConnection] = {}
        for agent_name in agent_names:
            config = AGENT_CONFIGS.get(agent_name)
            if not config:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported agent name: {agent_name}",
                )
            room = rtc.Room()
            await room.connect(
                ws_url,
                _build_agent_token(
                    api_key=api_key,
                    api_secret=api_secret,
                    room_name=room_name,
                    agent_name=agent_name,
                ),
            )
            # All sharks start as inactive; the first will be marked active below
            await room.local_participant.set_attributes({"shark.active": "false"})
            connections[agent_name] = SharkRoomConnection(
                room=room,
                agent_name=agent_name,
                config=config,
            )
            print(f"[Room] {agent_name} connected to {room_name}")

        # ── 2. Build the turn state BEFORE starting the first session ──
        #    (the session needs a reference to state for the turn-complete callback)
        state = SharkTurnState(
            connections=connections,
            turn_order=agent_names,
            current_turn_index=0,
            active_session=None,
            room_name=room_name,
            entrepreneur_identity=entrepreneur_identity,
        )
        TURN_STATES[room_name] = state

        # ── 3. Start only the first shark's session ──
        state.active_session = await _start_shark_session(
            connections[agent_names[0]], google_api_key, entrepreneur_identity, state
        )

    return sorted(agent_names)


@app.post("/token")
async def get_token(request: TokenRequest):
    api_key, api_secret, server_url = _get_livekit_credentials()
    try:
        room_name = _resolve_room_name(request)
        participant_token = _build_participant_token(
            request, api_key=api_key, api_secret=api_secret, room_name=room_name
        )
        return {
            "participant_token": participant_token,
            "server_url": server_url,
            "room_name": room_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session-token")
async def get_session_token(request: SessionTokenRequest):
    api_key, api_secret, server_url = _get_livekit_credentials()
    try:
        room_name = _resolve_room_name(request)
        requested_agents = request.agent_names or DEFAULT_AGENT_NAMES

        if not request.participant_identity:
            raise HTTPException(
                status_code=400, detail="participant_identity is required"
            )

        lkapi = api.LiveKitAPI(url=server_url, api_key=api_key, api_secret=api_secret)
        try:
            room_created = await _ensure_room(lkapi, room_name)
        finally:
            await lkapi.aclose()

        agents_connected = await _join_agents_manually(
            server_url=server_url,
            api_key=api_key,
            api_secret=api_secret,
            room_name=room_name,
            agent_names=requested_agents,
            entrepreneur_identity=request.participant_identity,
        )

        participant_token = _build_participant_token(
            request, api_key=api_key, api_secret=api_secret, room_name=room_name
        )

        state = TURN_STATES.get(room_name)
        current_shark = state.current_shark if state else requested_agents[0]

        return {
            "participant_token": participant_token,
            "server_url": server_url,
            "room_name": room_name,
            "room_created": room_created,
            "agents_requested": requested_agents,
            "agents_connected": agents_connected,
            "agents_dispatched": agents_connected,
            "current_shark": current_shark,
            "turn_order": requested_agents,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/advance-turn")
async def advance_turn(request: AdvanceTurnRequest):
    """
    Manual override: force-advance to the next shark without waiting for the
    conversation exchange limit. Useful for demos or if a shark gets stuck.
    """
    state = TURN_STATES.get(request.room_name)
    if not state:
        raise HTTPException(
            status_code=404,
            detail="Room not found or not yet initialised via /session-token",
        )
    # Cancel any in-progress auto-handoff by marking the current agent's flag
    if state.active_session:
        # Best-effort: if a SharkAgent is running, its _handoff_triggered will
        # prevent double-fire after we advance here.
        pass

    await _advance_turn_for_room(state)
    return {
        "current_shark": state.current_shark,
        "current_index": state.current_turn_index,
        "turn_order": state.turn_order,
    }


@app.get("/turn-status")
async def turn_status(room_name: str):
    state = TURN_STATES.get(room_name)
    if not state:
        raise HTTPException(status_code=404, detail="Room not found")
    return {
        "current_shark": state.current_shark,
        "current_index": state.current_turn_index,
        "turn_order": state.turn_order,
        "session_active": state.active_session is not None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
