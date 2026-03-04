import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers.session_router import router as session_router
from backend.routers.turn_router import router as turn_router

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router)
app.include_router(turn_router)

# Re-exports for backward compatibility (tests, etc.)
from backend.constants import AGENT_CONFIGS, MAX_EXCHANGES_PER_SHARK  # noqa: E402, F401
from backend.services.livekit_service import (  # noqa: E402, F401
    SharkRoomConnection,
    join_agents_manually,
)
from backend.services.shark_service import SharkAgent  # noqa: E402, F401
from backend.services.turn_service import (  # noqa: E402, F401
    TURN_STATES,
    SharkTurnState,
    advance_turn_for_room,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
