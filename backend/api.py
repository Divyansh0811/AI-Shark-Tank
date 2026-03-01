import logging

from backend.app import create_app

app = create_app()
logging.getLogger("shark_tank.turns").setLevel(logging.INFO)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
