from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

from livekit.agents import AgentSession

from backend.utils.shark_utils import build_shark_instructions

if TYPE_CHECKING:
    from backend.services.livekit_service import SharkRoomConnection


@dataclass
class SharkTurnState:
    """All runtime state for a single pitch room."""

    connections: Dict[str, SharkRoomConnection]
    turn_order: List[str]
    current_turn_index: int
    active_session: Optional[AgentSession]
    room_name: str
    entrepreneur_identity: str
    chat_ctx: object = None
    # One compressed summary entry per completed shark turn; grows slowly
    turn_summaries: List[str] = field(default_factory=list)
    # Message count at the start of the current turn (for delta extraction)
    turn_start_msg_count: int = 0
    advance_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def current_shark(self) -> str:
        return self.turn_order[self.current_turn_index]


TURN_STATES: Dict[str, SharkTurnState] = {}


async def start_shark_session(
    connection: SharkRoomConnection,
    google_api_key: str,
    entrepreneur_identity: str,
    turn_state: SharkTurnState,
) -> AgentSession:
    """Start an AgentSession for the given shark. Wires up the turn-complete callback."""
    from livekit.agents import room_io
    from livekit.plugins import google

    from backend.services.shark_service import SharkAgent

    config = connection.config
    # Build instructions that include Shark Tank context and any prior conversation
    instructions = build_shark_instructions(config, turn_state)

    async def on_turn_complete() -> None:
        await advance_turn_for_room(turn_state)

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            api_key=google_api_key,
            voice=config["voice"],
            temperature=config["temperature"],
            instructions=instructions,
        )
    )
    # Snapshot message count so _do_handoff knows which messages belong to this turn
    if turn_state.chat_ctx is not None:
        messages_fn = getattr(turn_state.chat_ctx, "messages", None)
        prior_msgs = messages_fn() if callable(messages_fn) else (messages_fn or [])
    else:
        prior_msgs = []
    turn_state.turn_start_msg_count = len(prior_msgs)

    await session.start(
        room=connection.room,
        agent=SharkAgent(
            connection.agent_name,
            instructions,
            on_turn_complete,
            turn_state,
            chat_ctx=turn_state.chat_ctx,
        ),
        room_options=room_io.RoomOptions(
            participant_identity=entrepreneur_identity,
            close_on_disconnect=False,
        ),
    )
    # Signal to the frontend that this shark is the active one
    await connection.room.local_participant.set_attributes({"shark.active": "true"})
    print(f"[Turn] Session started for {connection.agent_name}")
    return session


async def advance_turn_for_room(state: SharkTurnState) -> None:
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
                print(
                    f"[Turn] Warning: could not clear shark.active for {state.current_shark}: {e}"
                )

        # Close the outgoing session
        if state.active_session is not None:
            print(f"[Turn] Closing session for {state.current_shark}")
            await state.active_session.aclose()
            state.active_session = None

        # Advance turn index
        state.current_turn_index = (state.current_turn_index + 1) % len(
            state.turn_order
        )
        print(f"[Turn] It is now {state.current_shark}'s turn")

        # Start the new session
        next_conn = state.connections[state.current_shark]
        state.active_session = await start_shark_session(
            next_conn, google_api_key, state.entrepreneur_identity, state
        )
