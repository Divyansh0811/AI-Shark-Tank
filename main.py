from livekit.agents import AgentServer, AgentSession, Agent, room_io
from dotenv import load_dotenv

from livekit import agents, rtc, api
from livekit.plugins import (
    google,
    noise_cancellation,
)

load_dotenv(".env")
room_name = "shark-arena"
shark_a = "shark-a"
shark_b = "shark-b"
shark_c = "shark-c"

class Shark(Agent):
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
    print(f"Room name: {ctx.room.name}")
    print(f"Participants in room: {len(ctx.room.remote_participants)}")
    for rp in ctx.room.remote_participants.values():
        print(f" - Participant: {rp.identity} (Name: {rp.name}, Kind: {rp.kind})")

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

async def create_explicit_dispatch():
    lkapi = api.LiveKitAPI()
    try:
        try:
            dispatches = await lkapi.agent_dispatch.list_dispatch(room_name=room_name)
        except Exception as e:
            # If room doesn't exist, we assume no dispatches
            print(f"Room not found or error listing dispatches: {e}")
            dispatches = []
            
        existing_agents = {d.agent_name for d in dispatches}

        for agent in [shark_a, shark_b, shark_c]:
            if agent not in existing_agents:
                dispatch = await lkapi.agent_dispatch.create_dispatch(
                    api.CreateAgentDispatchRequest(
                        agent_name=agent,
                        room=room_name,
                    )
                )
                print(f"Dispatch created for {agent}: {dispatch.id}")
            else:
                # print(f"Dispatch already exists for {agent}")
                pass

        dispatches = await lkapi.agent_dispatch.list_dispatch(room_name=room_name)
        print(f"Total dispatches cnt: {len(dispatches)}")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    import asyncio
    asyncio.run(create_explicit_dispatch())
    agents.cli.run_app(server)