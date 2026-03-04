from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

from fastapi import HTTPException
from livekit import rtc

from backend.constants import AGENT_CONFIGS, AGENT_JOIN_LOCK
from backend.utils.livekit_utils import build_agent_token, normalize_ws_url


@dataclass
class SharkRoomConnection:
    """A persistent room connection for a single shark identity."""

    room: rtc.Room
    agent_name: str
    config: dict


async def join_agents_manually(
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
    from backend.services.turn_service import (
        TURN_STATES,
        SharkTurnState,
        start_shark_session,
    )

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not configured")

    ws_url = normalize_ws_url(server_url)

    async with AGENT_JOIN_LOCK:
        existing_state = TURN_STATES.get(room_name)
        if existing_state:
            all_connected = all(
                conn.room.isconnected() for conn in existing_state.connections.values()
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
                build_agent_token(
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
        state.active_session = await start_shark_session(
            connections[agent_names[0]], google_api_key, entrepreneur_identity, state
        )

    return sorted(agent_names)
