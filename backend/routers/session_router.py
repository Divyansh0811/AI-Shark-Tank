from fastapi import APIRouter

from backend.controllers.session_controller import get_session_token, get_token
from backend.schemas.shark import SessionTokenRequest, TokenRequest

router = APIRouter()


@router.post("/token")
async def token_endpoint(request: TokenRequest):
    return await get_token(request)


@router.post("/session-token")
async def session_token_endpoint(request: SessionTokenRequest):
    return await get_session_token(request)
