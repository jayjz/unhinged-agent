import pytest

from core.fsm import AgentState, StateMachine


@pytest.mark.asyncio
async def test_fsm_initial_state():
    fsm = StateMachine()
    assert fsm.current_state == AgentState.IDLE


@pytest.mark.asyncio
async def test_fsm_valid_transitions():
    fsm = StateMachine()

    # IDLE -> LISTENING
    success = await fsm.transition_to(AgentState.LISTENING)
    assert success is True
    assert fsm.current_state == AgentState.LISTENING

    # LISTENING -> PROCESSING
    success = await fsm.transition_to(AgentState.PROCESSING)
    assert success is True
    assert fsm.current_state == AgentState.PROCESSING

    # PROCESSING -> SPEAKING
    success = await fsm.transition_to(AgentState.SPEAKING)
    assert success is True
    assert fsm.current_state == AgentState.SPEAKING


@pytest.mark.asyncio
async def test_fsm_duplicate_transition_noop():
    fsm = StateMachine()
    await fsm.transition_to(AgentState.LISTENING)

    # Transitioning to the same state should return False
    success = await fsm.transition_to(AgentState.LISTENING)
    assert success is False
    assert fsm.current_state == AgentState.LISTENING
