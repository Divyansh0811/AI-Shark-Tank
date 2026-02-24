# agents/kevin.py
from livekit import agents, rtc
from livekit.agents import JobContext, AgentSession, room_io, Agent, AgentServer
from livekit.plugins import google, noise_cancellation
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

server = AgentServer()

class Kevin(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are Kevin O'Leary from Shark Tank. You are cynical, focused on royalties and margins.",
        )
    
    async def on_enter(self) -> None:
        await self.session.generate_reply(instructions="You are Kevin O'Leary, the Shark from Shark Tank. You are here to invest in businesses. Ask questions to the entrepreneur and decide whether to invest or not.")



@server.rtc_session()
async def kevin_session(ctx: JobContext):
    print(f"Kevin joining room {ctx.room.name}")
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            api_key=os.getenv("GOOGLE_API_KEY"),
            voice="Puck",
            temperature=0.6,
            instructions="You are a helpful assistant",
        ),
    )

    await session.start(
        room=ctx.room,
        agent=Kevin(),   
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony() if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP else noise_cancellation.BVC(),
            )
        )
    )

    await session.generate_reply(
        instructions="You are Kevin O'Leary, the Shark from Shark Tank. You are here to invest in businesses. Ask questions to the entrepreneur and decide whether to invest or not.",
    )

if __name__ == "__main__":
    agents.cli.run_app(server)