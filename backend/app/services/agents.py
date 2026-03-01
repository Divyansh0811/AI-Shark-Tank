import asyncio
import logging
import os
import random
from typing import List

from fastapi import HTTPException
from livekit import rtc
from livekit.agents import Agent, AgentSession, room_io
from livekit.plugins import google

from backend.app.config import (
    AGENT_CONFIGS,
    TURN_CONTEXT_WINDOW,
    TURN_MIN_TRANSCRIPT_CHARS,
)
from backend.app.services.event_bus import EventBus
from backend.app.services.livekit import build_agent_token, normalize_ws_url
from backend.app.state import (
    ACTIVE_AGENT_CONNECTIONS,
    AGENT_JOIN_LOCK,
    ROOM_TURN_STATES,
    ManagedAgentConnection,
    RoomTurnState,
)

logger = logging.getLogger("shark_tank.turns")


class SharkAgent(Agent):
    def __init__(self, instructions: str):
        super().__init__(instructions=instructions)

    async def on_enter(self) -> None:
        return


def ensure_turn_state(room_name: str, agent_names: List[str]) -> RoomTurnState:
    state = ROOM_TURN_STATES.get(room_name)
    if state:
        state.agent_order = agent_names
        if state.next_agent_idx >= len(agent_names):
            state.next_agent_idx = 0
        return state

    state = RoomTurnState(
        agent_order=agent_names,
        founder_identity=None,
        next_agent_idx=0,
        shared_context=[],
        last_handled_turn_key="",
        awaiting_reply_from=None,
        greeted=False,
        orchestrator_wired=False,
        event_bus=EventBus(),
        lock=asyncio.Lock(),
    )
    ROOM_TURN_STATES[room_name] = state
    return state


def _sync_audio_subscriptions(room_name: str, state: RoomTurnState) -> None:
    if not state.agent_order:
        return

    selected_agent = state.agent_order[state.next_agent_idx]
    for agent_name in state.agent_order:
        conn = ACTIVE_AGENT_CONNECTIONS.get((room_name, agent_name))
        if not conn:
            continue

        audio_input = conn.session.input.audio
        set_participant = getattr(audio_input, "set_participant", None)
        if not callable(set_participant):
            continue

        if agent_name == selected_agent and state.founder_identity:
            set_participant(state.founder_identity)
        else:
            set_participant(None)


def _pick_next_listener(state: RoomTurnState, current_agent: str) -> None:
    if not state.agent_order:
        return
    candidates = [name for name in state.agent_order if name != current_agent]
    if not candidates:
        return
    next_name = random.choice(candidates)
    state.next_agent_idx = state.agent_order.index(next_name)


async def handle_user_turn(
    *,
    room_name: str,
    triggering_agent: str,
    session: AgentSession,
    state: RoomTurnState,
    transcript: str,
    speaker_id: str | None,
) -> None:
    async with state.lock:
        selected_agent = state.agent_order[state.next_agent_idx]
        normalized_text = " ".join(transcript.strip().split())
        turn_key = f"{speaker_id or 'unknown'}::{normalized_text.lower()}"
        logger.info(
            "turn-event room=%s trigger=%s selected=%s key=%s",
            room_name,
            triggering_agent,
            selected_agent,
            turn_key,
        )

        if triggering_agent != selected_agent:
            logger.info(
                "turn-drop not-selected room=%s trigger=%s selected=%s",
                room_name,
                triggering_agent,
                selected_agent,
            )
            return

        if (
            speaker_id
            and state.founder_identity
            and speaker_id != state.founder_identity
        ):
            logger.info(
                "turn-drop non-founder room=%s trigger=%s speaker=%s founder=%s",
                room_name,
                triggering_agent,
                speaker_id,
                state.founder_identity,
            )
            return

        if len(normalized_text) < TURN_MIN_TRANSCRIPT_CHARS:
            logger.info(
                "turn-drop short room=%s trigger=%s chars=%s text=%s",
                room_name,
                triggering_agent,
                len(normalized_text),
                normalized_text,
            )
            return

        if turn_key == state.last_handled_turn_key:
            logger.info(
                "turn-drop duplicate room=%s trigger=%s selected=%s",
                room_name,
                triggering_agent,
                selected_agent,
            )
            return

        if state.awaiting_reply_from is not None:
            logger.info(
                "turn-drop awaiting-reply room=%s trigger=%s awaiting=%s",
                room_name,
                triggering_agent,
                state.awaiting_reply_from,
            )
            return

        state.last_handled_turn_key = turn_key
        state.awaiting_reply_from = triggering_agent
        state.shared_context.append(normalized_text)
        if len(state.shared_context) > TURN_CONTEXT_WINDOW:
            state.shared_context = state.shared_context[-TURN_CONTEXT_WINDOW:]

        context_block = "\n".join(
            f"- Founder said: {line}" for line in state.shared_context[-TURN_CONTEXT_WINDOW:]
        )

        session.generate_reply(
            user_input=normalized_text,
            input_modality="text",
            instructions=(
                "You are in a Shark Tank panel with other sharks. Keep your reply concise "
                "and directly continue the founder's pitch context.\n"
                f"Recent founder context:\n{context_block}"
            ),
        )
        logger.info(
            "turn-commit room=%s trigger=%s selected=%s text=%s",
            room_name,
            triggering_agent,
            selected_agent,
            normalized_text,
        )


async def _wire_room_orchestrator(room_name: str, state: RoomTurnState) -> None:
    if state.orchestrator_wired:
        return

    async def on_founder_turn_completed(data: dict) -> None:
        agent_name = data["agent_name"]
        transcript = data["transcript"]
        speaker_id = data.get("speaker_id")
        conn = ACTIVE_AGENT_CONNECTIONS.get((room_name, agent_name))
        if not conn:
            return
        await handle_user_turn(
            room_name=room_name,
            triggering_agent=agent_name,
            session=conn.session,
            state=state,
            transcript=transcript,
            speaker_id=speaker_id,
        )

    async def on_agent_reply_completed(data: dict) -> None:
        agent_name = data["agent_name"]
        async with state.lock:
            if state.awaiting_reply_from != agent_name:
                logger.info(
                    "listener-rotate skip room=%s trigger=%s awaiting=%s",
                    room_name,
                    agent_name,
                    state.awaiting_reply_from,
            )
                return
            state.awaiting_reply_from = None
            _pick_next_listener(state, agent_name)
            _sync_audio_subscriptions(room_name, state)
            logger.info(
                "listener-rotate room=%s from=%s to=%s",
                room_name,
                agent_name,
                state.agent_order[state.next_agent_idx],
            )

    await state.event_bus.subscribe("founder_turn_completed", on_founder_turn_completed)
    await state.event_bus.subscribe("agent_reply_completed", on_agent_reply_completed)
    state.orchestrator_wired = True


def wire_shared_context_turn_gating(
    *,
    room_name: str,
    agent_name: str,
    session: AgentSession,
    state: RoomTurnState,
) -> None:
    def on_conversation_item_added(ev) -> None:
        item = getattr(ev, "item", None)
        if not item:
            return
        if getattr(item, "role", None) != "user":
            return

        text_content = getattr(item, "text_content", "")
        if callable(text_content):
            text_content = text_content()
        transcript = (text_content or "").strip()
        if not transcript:
            return
        if transcript.lower() in {"[noise]", "(noise)", "noise"}:
            logger.info(
                "item-drop noise room=%s agent=%s text=%s",
                room_name,
                agent_name,
                transcript,
            )
            return

        selected_agent = state.agent_order[state.next_agent_idx]
        if agent_name != selected_agent:
            logger.info(
                "item-drop non-selected room=%s agent=%s selected=%s text=%s",
                room_name,
                agent_name,
                selected_agent,
                transcript,
            )
            return

        logger.info(
            "conversation-item room=%s agent=%s role=user text=%s",
            room_name,
            agent_name,
            transcript,
        )
        asyncio.create_task(
            state.event_bus.emit(
                "founder_turn_completed",
                {
                    "room_name": room_name,
                    "agent_name": agent_name,
                    "transcript": transcript,
                    "speaker_id": None,
                },
            )
        )

    def on_agent_state_changed(ev) -> None:
        new_state = getattr(ev, "new_state", None)
        if new_state not in {"listening", "idle"}:
            return

        asyncio.create_task(
            state.event_bus.emit(
                "agent_reply_completed",
                {
                    "room_name": room_name,
                    "agent_name": agent_name,
                },
            )
        )

    session.on("conversation_item_added", on_conversation_item_added)
    session.on("agent_state_changed", on_agent_state_changed)


async def join_agents_manually(
    *,
    server_url: str,
    api_key: str,
    api_secret: str,
    room_name: str,
    agent_names: List[str],
    founder_identity: str | None,
) -> List[str]:
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not configured")

    ws_url = normalize_ws_url(server_url)
    connected_agents: List[str] = []
    state = ensure_turn_state(room_name, agent_names)
    state.founder_identity = founder_identity
    await _wire_room_orchestrator(room_name, state)

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
                build_agent_token(
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
                ),
            )
            await session.start(
                room=room,
                agent=SharkAgent(config["instructions"]),
                room_options=room_io.RoomOptions(
                    text_input=False,
                    participant_kinds=[
                        rtc.ParticipantKind.Value("PARTICIPANT_KIND_STANDARD")
                    ],
                    participant_identity=(
                        founder_identity
                        if agent_name == state.agent_order[state.next_agent_idx]
                        else "__muted__"
                    ),
                ),
            )

            wire_shared_context_turn_gating(
                room_name=room_name,
                agent_name=agent_name,
                session=session,
                state=state,
            )

            ACTIVE_AGENT_CONNECTIONS[key] = ManagedAgentConnection(
                agent_name=agent_name,
                room=room,
                session=session,
            )
            connected_agents.append(agent_name)

        _sync_audio_subscriptions(room_name, state)

        if not state.greeted and agent_names:
            opener_name = state.agent_order[0]
            opener = ACTIVE_AGENT_CONNECTIONS.get((room_name, opener_name))
            if opener:
                opener.session.generate_reply(
                    instructions=(
                        "Greet the founder briefly as the first shark to speak and ask "
                        "for a concise 30-second pitch."
                    ),
                    input_modality="text",
                )
                state.greeted = True

    return sorted(connected_agents)
