from pydantic import BaseModel


class AdvanceTurnRequest(BaseModel):
    room_name: str
