from __future__ import annotations

import asyncio
from typing import Callable, Coroutine

from livekit.agents import Agent

from backend.constants import MAX_EXCHANGES_PER_SHARK
from backend.utils.shark_utils import build_turn_summary


class SharkAgent(Agent):
    """
    A shark that listens for MAX_EXCHANGES_PER_SHARK user messages then
    generates a farewell and hands off to the next shark automatically.
    """

    def __init__(
        self,
        name: str,
        instructions: str,
        on_turn_complete: Callable[[], Coroutine],
        turn_state=None,
        chat_ctx=None,
    ):
        super().__init__(instructions=instructions, chat_ctx=chat_ctx)
        self._name = name
        self._on_turn_complete = on_turn_complete
        self._turn_state = turn_state
        self._user_msg_count = 0
        self._handoff_triggered = False

    async def on_enter(self) -> None:
        self.session.on("conversation_item_added", self._on_conversation_item)
        has_prior = bool(self._turn_state and self._turn_state.turn_summaries)
        if has_prior:
            await self.session.generate_reply(
                instructions=(
                    f"You are {self._name} and you are LIVE on Shark Tank right now. "
                    "You have been listening to this entrepreneur's pitch. "
                    "Introduce yourself briefly, then ask a sharp follow-up question "
                    "that digs into an angle the previous sharks have not yet explored."
                )
            )
        else:
            await self.session.generate_reply(
                instructions=(
                    f"You are {self._name} and you are LIVE on Shark Tank right now. "
                    "Welcome the entrepreneur to the Tank, introduce yourself, "
                    "and ask your first key question about their business."
                )
            )

    async def on_exit(self) -> None:
        if self._turn_state is not None:
            self._turn_state.chat_ctx = self.chat_ctx
        self.session.off("conversation_item_added", self._on_conversation_item)

    def _on_conversation_item(self, ev) -> None:
        # Always keep shared state's chat_ctx updated
        if self._turn_state is not None:
            self._turn_state.chat_ctx = self.chat_ctx
        if self._handoff_triggered:
            return
        # Only count final user (entrepreneur) messages
        role = getattr(ev.item, "role", None)
        if role == "user":
            self._user_msg_count += 1
            print(
                f"[Turn] {self._name}: user message "
                f"{self._user_msg_count}/{MAX_EXCHANGES_PER_SHARK}"
            )
            if self._user_msg_count >= MAX_EXCHANGES_PER_SHARK:
                self._handoff_triggered = True
                asyncio.create_task(self._do_handoff())

    async def _do_handoff(self) -> None:
        """Generate a farewell, compress this turn into a summary, then advance."""
        print(f"[Turn] {self._name} wrapping up, handing off...")
        await self.session.generate_reply(
            instructions=(
                "Wrap up your questioning with one concise final thought. "
                "Tell the entrepreneur you're passing them to your fellow shark."
            )
        )
        # Save full context so next shark's Agent has the raw history
        if self._turn_state is not None:
            self._turn_state.chat_ctx = self.chat_ctx
            # Compress this turn into a summary block (only the delta since turn start)
            summary = build_turn_summary(
                self._name, self.chat_ctx, self._turn_state.turn_start_msg_count
            )
            if summary:
                self._turn_state.turn_summaries.append(summary)
                print(f"[Turn] Saved summary for {self._name} ({len(summary)} chars)")
        await self._on_turn_complete()
