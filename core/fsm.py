import asyncio
from enum import Enum, auto

from loguru import logger


class AgentState(Enum):
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    ERROR = auto()


class StateMachine:
    def __init__(self):
        self._state = AgentState.IDLE
        self._lock = asyncio.Lock()

    @property
    def current_state(self) -> AgentState:
        return self._state

    async def transition_to(self, new_state: AgentState) -> bool:
        async with self._lock:
            if self._state == new_state:
                return False
            logger.info(f"State Transition: {self._state.name} -> {new_state.name}")
            self._state = new_state
            return True

    def reset(self):
        self._state = AgentState.IDLE
