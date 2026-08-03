import asyncio
from enum import Enum, auto

from loguru import logger


class AgentState(Enum):
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    ERROR = auto()


class InvalidTransition(RuntimeError):
    pass


_ALLOWED_TRANSITIONS = {
    AgentState.IDLE: {AgentState.LISTENING, AgentState.ERROR},
    AgentState.LISTENING: {
        AgentState.PROCESSING,
        AgentState.IDLE,
        AgentState.ERROR,
    },
    AgentState.PROCESSING: {
        AgentState.SPEAKING,
        AgentState.LISTENING,
        AgentState.IDLE,
        AgentState.ERROR,
    },
    AgentState.SPEAKING: {
        AgentState.LISTENING,
        AgentState.IDLE,
        AgentState.ERROR,
    },
    AgentState.ERROR: {AgentState.IDLE},
}


class StateMachine:
    def __init__(self) -> None:
        self._state = AgentState.IDLE
        self._lock = asyncio.Lock()

    @property
    def current_state(self) -> AgentState:
        return self._state

    async def transition_to(self, new_state: AgentState) -> bool:
        async with self._lock:
            if self._state == new_state:
                return False
            if new_state not in _ALLOWED_TRANSITIONS[self._state]:
                raise InvalidTransition(
                    f"Invalid agent transition: {self._state.name} -> {new_state.name}"
                )
            logger.info("State transition: {} -> {}", self._state.name, new_state.name)
            self._state = new_state
            return True

    async def reset(self) -> None:
        async with self._lock:
            self._state = AgentState.IDLE
