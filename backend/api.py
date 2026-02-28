import asyncio
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from livekit import api, rtc
from livekit.agents import Agent, AgentSession
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


class TokenRequest(BaseModel):
    room_name: Optional[str] = None
    participant_identity: Optional[str] = None
    participant_name: Optional[str] = None
    participant_metadata: Optional[str] = None
    participant_attributes: Optional[Dict[str, str]] = None
    room_config: Optional[dict] = None


class SessionTokenRequest(TokenRequest):
    agent_names: Optional[List[str]] = None


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
class ManagedAgentConnection:
    room: rtc.Room
    session: AgentSession


ACTIVE_AGENT_CONNECTIONS: Dict[Tuple[str, str], ManagedAgentConnection] = {}


class SharkAgent(Agent):
    def __init__(self, instructions: str):
        super().__init__(instructions=instructions)

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Introduce yourself as this shark and ask the entrepreneur "
                "their first key business question."
            )
        )


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
        return "wss://" + url[len("https://") :]
    if url.startswith("http://"):
        return "ws://" + url[len("http://") :]
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


async def _join_agents_manually(
    *,
    server_url: str,
    api_key: str,
    api_secret: str,
    room_name: str,
    agent_names: List[str],
) -> List[str]:
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not configured")

    ws_url = _normalize_ws_url(server_url)
    connected_agents: List[str] = []

    async with AGENT_JOIN_LOCK:
        for agent_name in agent_names:
            config = AGENT_CONFIGS.get(agent_name)
            if not config:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported agent name: {agent_name}",
                )

            key = (room_name, agent_name)
            existing = ACTIVE_AGENT_CONNECTIONS.get(key)
            if existing and existing.room.isconnected():
                connected_agents.append(agent_name)
                continue

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

            session = AgentSession(
                llm=google.realtime.RealtimeModel(
                    api_key=google_api_key,
                    voice=config["voice"],
                    temperature=config["temperature"],
                    instructions=config["instructions"],
                )
            )
            await session.start(room=room, agent=SharkAgent(config["instructions"]))

            ACTIVE_AGENT_CONNECTIONS[key] = ManagedAgentConnection(
                room=room, session=session
            )
            connected_agents.append(agent_name)

    return sorted(connected_agents)


@app.post("/token")
async def get_token(request: TokenRequest):
    api_key, api_secret, server_url = _get_livekit_credentials()

    try:
        room_name = _resolve_room_name(request)
        participant_token = _build_participant_token(
            request,
            api_key=api_key,
            api_secret=api_secret,
            room_name=room_name,
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

        lkapi = api.LiveKitAPI(
            url=server_url,
            api_key=api_key,
            api_secret=api_secret,
        )
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
        )

        participant_token = _build_participant_token(
            request,
            api_key=api_key,
            api_secret=api_secret,
            room_name=room_name,
        )

        return {
            "participant_token": participant_token,
            "server_url": server_url,
            "room_name": room_name,
            "room_created": room_created,
            "agents_requested": requested_agents,
            "agents_connected": agents_connected,
            "agents_dispatched": agents_connected,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
