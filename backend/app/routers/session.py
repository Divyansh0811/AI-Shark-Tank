from fastapi import APIRouter, HTTPException
from livekit import api as lk_api

from backend.app.config import DEFAULT_AGENT_NAMES, get_livekit_credentials
from backend.app.schemas import SessionTokenRequest, TokenRequest
from backend.app.services.agents import join_agents_manually
from backend.app.services.livekit import (
    build_participant_token,
    ensure_room,
    resolve_room_name,
)

router = APIRouter()


@router.post("/token")
async def get_token(request: TokenRequest):
    api_key, api_secret, server_url = get_livekit_credentials()

    try:
        room_name = resolve_room_name(request)
        participant_token = build_participant_token(
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/session-token")
async def get_session_token(request: SessionTokenRequest):
    api_key, api_secret, server_url = get_livekit_credentials()

    try:
        room_name = resolve_room_name(request)
        requested_agents = request.agent_names or DEFAULT_AGENT_NAMES

        lkapi = lk_api.LiveKitAPI(
            url=server_url,
            api_key=api_key,
            api_secret=api_secret,
        )
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
            founder_identity=request.participant_identity,
        )

        participant_token = build_participant_token(
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
