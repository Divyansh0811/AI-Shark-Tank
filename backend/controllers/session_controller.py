from fastapi import HTTPException
from livekit import api

from backend.constants import DEFAULT_AGENT_NAMES
from backend.schemas.shark import SessionTokenRequest, TokenRequest
from backend.services.livekit_service import join_agents_manually
from backend.services.turn_service import TURN_STATES
from backend.utils.livekit_utils import (
    build_participant_token,
    ensure_room,
    get_livekit_credentials,
)
from backend.utils.turn_utils import resolve_room_name


async def get_token(request: TokenRequest) -> dict:
    api_key, api_secret, server_url = get_livekit_credentials()
    try:
        room_name = resolve_room_name(request)
        participant_token = build_participant_token(
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


async def get_session_token(request: SessionTokenRequest) -> dict:
    api_key, api_secret, server_url = get_livekit_credentials()
    try:
        room_name = resolve_room_name(request)
        requested_agents = request.agent_names or DEFAULT_AGENT_NAMES

        if not request.participant_identity:
            raise HTTPException(
                status_code=400, detail="participant_identity is required"
            )

        lkapi = api.LiveKitAPI(url=server_url, api_key=api_key, api_secret=api_secret)
        try:
            room_created = await ensure_room(lkapi, room_name)
        finally:
            await lkapi.aclose()

        agents_connected = await join_agents_manually(
            server_url=server_url,
            api_key=api_key,
            api_secret=api_secret,
            room_name=room_name,
            agent_names=requested_agents,
            entrepreneur_identity=request.participant_identity,
        )

        participant_token = build_participant_token(
            request, api_key=api_key, api_secret=api_secret, room_name=room_name
        )

        state = TURN_STATES.get(room_name)
        current_shark = state.current_shark if state else requested_agents[0]
        turn_order = state.turn_order if state else requested_agents

        return {
            "participant_token": participant_token,
            "server_url": server_url,
            "room_name": room_name,
            "room_created": room_created,
            "agents_requested": requested_agents,
            "agents_connected": agents_connected,
            "agents_dispatched": agents_connected,
            "current_shark": current_shark,
            "turn_order": turn_order,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
