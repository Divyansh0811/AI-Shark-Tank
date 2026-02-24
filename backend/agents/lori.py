# agents/mark.py
from livekit import agents, rtc
from livekit.agents import JobContext, AgentSession, room_io, Agent, AgentServer
from livekit.plugins import google, noise_cancellation
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

server = AgentServer()

class Lori(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are Lori Greiner from Shark Tank. Queen of QVC. You look for 'hero' products with mass-market appeal.",
        )
    
    async def on_enter(self) -> None:
        await self.session.generate_reply(instructions="You are Lori Greiner, the Queen of QVC. You look for 'hero' products with mass-market appeal.")



@server.rtc_session()
async def lori_session(ctx: JobContext):
    print(f"Lori joining room {ctx.room.name}")
    
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            voice="Kore",
            temperature=0.8,
            instructions="You are Lori Greiner, the Queen of QVC. You look for 'hero' products with mass-market appeal.",
        ),
    )
    
    print(f"Room name: {ctx.room.name}")
    print(f"Participants in room: {len(ctx.room.remote_participants)}")
    for rp in ctx.room.remote_participants.values():
        print(f" - Participant: {rp.identity} (Name: {rp.name}, Kind: {rp.kind})")

    await session.start(
        room=ctx.room,
        agent=Lori(),   
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony() if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP else noise_cancellation.BVC(),
            )
        )
    )

    await session.generate_reply(
        instructions="You are Lori Greiner, the Queen of QVC. You look for 'hero' products with mass-market appeal.",
    )

if __name__ == "__main__":
    agents.cli.run_app(server)