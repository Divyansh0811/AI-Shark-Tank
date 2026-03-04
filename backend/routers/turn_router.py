from fastapi import APIRouter

from backend.controllers.turn_controller import advance_turn, turn_status
from backend.schemas.turn import AdvanceTurnRequest

router = APIRouter()


@router.post("/advance-turn")
async def advance_turn_endpoint(request: AdvanceTurnRequest):
    return await advance_turn(request)


@router.get("/turn-status")
async def turn_status_endpoint(room_name: str):
    return await turn_status(room_name)
