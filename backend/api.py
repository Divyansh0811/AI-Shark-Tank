from typing import Optional, Dict
from livekit.protocol.agent_dispatch import RoomAgentDispatch
from livekit.protocol.room import RoomConfiguration
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from livekit import api
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = FastAPI()

# Add CORS middleware to allow requests from frontend (e.g., Vite/Next.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TokenRequest(BaseModel):
    room_name: Optional[str] = None
    participant_identity: Optional[str] = None
    participant_name: Optional[str] = None
    participant_metadata: Optional[str] = None
    participant_attributes: Optional[Dict[str, str]] = None
    room_config: Optional[dict] = None

@app.post("/token")
async def get_token(
    request: TokenRequest
):
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    server_url = os.getenv("LIVEKIT_URL")

    if not all([api_key, api_secret, server_url]):
        raise HTTPException(status_code=500, detail="LiveKit credentials not configured")

    room_name = request.room_name
    participant_identity = request.participant_identity
    participant_name = request.participant_name or "anonymous"

    try:
        # Extract room name from config if not provided directly
        effective_room_name = room_name
        if not effective_room_name and request.room_config and "name" in request.room_config:
            effective_room_name = request.room_config["name"]

        token = api.AccessToken(api_key, api_secret) \
            .with_identity(participant_identity) \
            .with_name(participant_name) \
            .with_grants(api.VideoGrants(
                room_join=True,
                room=effective_room_name,
                can_publish=True,
                can_subscribe=True,
            ))
        
        if request.participant_metadata:
            token = token.with_metadata(request.participant_metadata)
        if request.participant_attributes:
            token = token.with_attributes(request.participant_attributes)
        if request.room_config:
            token = token.with_room_config(
                RoomConfiguration(
                    name=request.room_config.get("name", effective_room_name),
                    empty_timeout=request.room_config.get("empty_timeout"),
                )
            )

        participant_token = token.to_jwt()

        return {
            "participant_token": participant_token,
            "server_url": server_url,
        }
    
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
