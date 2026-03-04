from fastapi import HTTPException

from backend.schemas.turn import AdvanceTurnRequest
from backend.services.turn_service import TURN_STATES, advance_turn_for_room


async def advance_turn(request: AdvanceTurnRequest) -> dict:
    """
    Manual override: force-advance to the next shark without waiting for the
    conversation exchange limit. Useful for demos or if a shark gets stuck.
    """
    state = TURN_STATES.get(request.room_name)
    if not state:
        raise HTTPException(
            status_code=404,
            detail="Room not found or not yet initialised via /session-token",
        )
    # Cancel any in-progress auto-handoff by marking the current agent's flag
    if state.active_session:
        # Best-effort: if a SharkAgent is running, its _handoff_triggered will
        # prevent double-fire after we advance here.
        pass

    await advance_turn_for_room(state)
    return {
        "current_shark": state.current_shark,
        "current_index": state.current_turn_index,
        "turn_order": state.turn_order,
    }


async def turn_status(room_name: str) -> dict:
    state = TURN_STATES.get(room_name)
    if not state:
        raise HTTPException(status_code=404, detail="Room not found")
    return {
        "current_shark": state.current_shark,
        "current_index": state.current_turn_index,
        "turn_order": state.turn_order,
        "session_active": state.active_session is not None,
    }
