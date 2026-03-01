from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers.session import router as session_router


def create_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(session_router)
    return app
