from livekit import api
from livekit.protocol.room import RoomConfiguration

from backend.app.schemas import TokenRequest


def normalize_ws_url(url: str) -> str:
    if url.startswith("https://"):
        return "wss://" + url[len("https://") :]
    if url.startswith("http://"):
        return "ws://" + url[len("http://") :]
    return url


def resolve_room_name(request: TokenRequest) -> str:
    effective_room_name = request.room_name
    if (
        not effective_room_name
        and request.room_config
        and "name" in request.room_config
    ):
        effective_room_name = request.room_config["name"]
    if not effective_room_name:
        raise ValueError("room_name is required")
    return effective_room_name


def build_participant_token(
    request: TokenRequest,
    *,
    api_key: str,
    api_secret: str,
    room_name: str,
) -> str:
    participant_identity = request.participant_identity
    if not participant_identity:
        raise ValueError("participant_identity is required")

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


async def ensure_room(lkapi: api.LiveKitAPI, room_name: str) -> bool:
    rooms_response = await lkapi.room.list_rooms(
        api.ListRoomsRequest(names=[room_name])
    )
    existing_rooms = getattr(rooms_response, "rooms", [])
    if existing_rooms:
        return False
    await lkapi.room.create_room(api.CreateRoomRequest(name=room_name))
    return True


def build_agent_token(
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
