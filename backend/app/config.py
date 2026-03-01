import os
from pathlib import Path
from typing import Tuple

from dotenv import load_dotenv
from fastapi import HTTPException

# Load backend/.env once for the entire backend package.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEFAULT_AGENT_NAMES = ["Mark", "Kevin", "Lori"]
AGENT_CONFIGS = {
    "Mark": {
        "voice": "Puck",
        "temperature": 0.6,
        "instructions": (
            "You are Mark Cuban from Shark Tank. You are bold, tech-focused, and "
            "look for scalability."
        ),
    },
    "Kevin": {
        "voice": "Puck",
        "temperature": 0.6,
        "instructions": (
            "You are Kevin O'Leary from Shark Tank. You are cynical, focused on "
            "royalties and margins."
        ),
    },
    "Lori": {
        "voice": "Kore",
        "temperature": 0.8,
        "instructions": (
            "You are Lori Greiner from Shark Tank. Queen of QVC. You look for hero "
            "products with mass-market appeal."
        ),
    },
}
TURN_MIN_TRANSCRIPT_CHARS = 3
TURN_CONTEXT_WINDOW = 6


def get_livekit_credentials() -> Tuple[str, str, str]:
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    server_url = os.getenv("LIVEKIT_URL")
    if not all([api_key, api_secret, server_url]):
        raise HTTPException(
            status_code=500, detail="LiveKit credentials not configured"
        )
    return api_key, api_secret, server_url
