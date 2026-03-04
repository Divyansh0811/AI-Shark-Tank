from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from backend.schemas.shark import TokenRequest


def resolve_room_name(request: TokenRequest) -> str:
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
