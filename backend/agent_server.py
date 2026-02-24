import os
from dotenv import load_dotenv

# MUST load env before initializing AgentServer or importing agent logic
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

from livekit.agents import cli, AgentServer
from agents.mark import mark_session
from agents.kevin import kevin_session
from agents.lori import lori_session

server = AgentServer()

@server.rtc_session(agent_name="Mark")
async def register_mark(ctx):
    await mark_session(ctx)

@server.rtc_session(agent_name="Kevin")
async def register_kevin(ctx):
    await kevin_session(ctx)

@server.rtc_session(agent_name="Lori")
async def register_lori(ctx):
    await lori_session(ctx)

if __name__ == "__main__":
    cli.run_app(server)