import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Protocol


class TurnManager(Protocol):
    async def try_acquire(self, room: str, agent: str, ttl_seconds: int) -> bool: ...

    async def get_current(self, room: str) -> Optional[str]: ...

    async def release(self, room: str, agent: str) -> bool: ...


@dataclass
class _MemoryTurn:
    agent: str
    expires_at: float


class InMemoryTurnManager:
    def __init__(self) -> None:
        self._turns: dict[str, _MemoryTurn] = {}
        self._lock = asyncio.Lock()

    async def try_acquire(self, room: str, agent: str, ttl_seconds: int) -> bool:
        now = time.time()
        async with self._lock:
            current = self._turns.get(room)
            if current and current.expires_at > now:
                return False
            self._turns[room] = _MemoryTurn(agent=agent, expires_at=now + ttl_seconds)
            return True

    async def get_current(self, room: str) -> Optional[str]:
        now = time.time()
        async with self._lock:
            current = self._turns.get(room)
            if not current:
                return None
            if current.expires_at <= now:
                self._turns.pop(room, None)
                return None
            return current.agent

    async def release(self, room: str, agent: str) -> bool:
        async with self._lock:
            current = self._turns.get(room)
            if not current:
                return False
            if current.agent != agent:
                return False
            self._turns.pop(room, None)
            return True


class RedisTurnManager:
    def __init__(self, redis_url: str) -> None:
        try:
            from redis.asyncio import from_url  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "redis package not installed; add dependency 'redis>=5.0'"
            ) from exc

        self._redis = from_url(redis_url, decode_responses=True)

    def _turn_key(self, room: str) -> str:
        return f"turnlock:{room}"

    async def try_acquire(self, room: str, agent: str, ttl_seconds: int) -> bool:
        key = self._turn_key(room)
        acquired = await self._redis.set(key, agent, ex=ttl_seconds, nx=True)
        return acquired is True or acquired == "OK"

    async def get_current(self, room: str) -> Optional[str]:
        return await self._redis.get(self._turn_key(room))

    async def release(self, room: str, agent: str) -> bool:
        key = self._turn_key(room)
        current = await self._redis.get(key)
        if current != agent:
            return False
        await self._redis.delete(key)
        return True


def create_turn_manager(redis_url: str | None) -> TurnManager:
    if redis_url:
        return RedisTurnManager(redis_url)
    return InMemoryTurnManager()
