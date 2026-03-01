import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from livekit import rtc
from livekit.agents import AgentSession

from backend.app.services.event_bus import EventBus


@dataclass
class ManagedAgentConnection:
    agent_name: str
    room: rtc.Room
    session: AgentSession


@dataclass
class RoomTurnState:
    agent_order: List[str]
    founder_identity: Optional[str]
    next_agent_idx: int
    shared_context: List[str]
    last_handled_turn_key: str
    awaiting_reply_from: Optional[str]
    greeted: bool
    orchestrator_wired: bool
    event_bus: EventBus
    lock: asyncio.Lock


ACTIVE_AGENT_CONNECTIONS: Dict[Tuple[str, str], ManagedAgentConnection] = {}
ROOM_TURN_STATES: Dict[str, RoomTurnState] = {}
AGENT_JOIN_LOCK = asyncio.Lock()
