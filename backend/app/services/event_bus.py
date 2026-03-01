import asyncio
from collections import defaultdict
from typing import Awaitable, Callable, DefaultDict


EventCallback = Callable[[dict], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._listeners: DefaultDict[str, list[EventCallback]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, event: str, callback: EventCallback) -> None:
        async with self._lock:
            self._listeners[event].append(callback)

    async def emit(self, event: str, data: dict) -> None:
        async with self._lock:
            listeners = list(self._listeners.get(event, []))

        for callback in listeners:
            await callback(data)
