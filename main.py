from livekit.agents import AgentServer, AgentSession, Agent, room_io
from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.plugins import (
    google,
    noise_cancellation,
)

load_dotenv(".env.local")

class Shark(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a shark from the show Shark Tank. You are here to invest in businesses. Ask questions to the entrepreneur and decide whether to invest or not.")

class SharkB(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a shark from the show Shark Tank. You are here to invest in businesses. Ask questions to the entrepreneur and decide whether to invest or not.")

class SharkC(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a shark from the show Shark Tank. You are here to invest in businesses. Ask questions to the entrepreneur and decide whether to invest or not.")

server = AgentServer()

@server.rtc_session(agent_name="Shark")
async def shark_session(ctx: agents.JobContext):
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            voice="Puck",
            temperature=0.8,
            instructions="You are a helpful assistant",
        ),
    )
    
    await session.start(
        room=ctx.room,
        agent=Shark(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony() if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP else noise_cancellation.BVC(),
            )
        )
    )

    await session.generate_reply(
        instructions="You are a shark from the show Shark Tank. You are here to invest in businesses. Ask questions to the entrepreneur and decide whether to invest or not.",
        
    )

if __name__ == "__main__":
    agents.cli.run_app(server)