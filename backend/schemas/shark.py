from typing import Dict, List, Optional

from pydantic import BaseModel


class TokenRequest(BaseModel):
    room_name: Optional[str] = None
    participant_identity: Optional[str] = None
    participant_name: Optional[str] = None
    participant_metadata: Optional[str] = None
    participant_attributes: Optional[Dict[str, str]] = None
    room_config: Optional[dict] = None


class SessionTokenRequest(TokenRequest):
    agent_names: Optional[List[str]] = None
