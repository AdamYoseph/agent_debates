# tests/test_debate.py
import pytest
from debate import DebateState, DebatePhase

def test_initial_state():
    state = DebateState(topic="Best family SUV")
    assert state.phase == DebatePhase.DEBATING
    assert state.round == 0
    assert state.history == []

def test_add_message():
    state = DebateState(topic="Best family SUV")
    state.add_message("Alpha", "I think the Honda CR-V is best.")
    assert len(state.history) == 1
    assert state.history[0]["name"] == "Alpha"

def test_increment_round():
    state = DebateState(topic="Best family SUV")
    state.increment_round()
    assert state.round == 1

def test_should_pause_after_max_rounds():
    state = DebateState(topic="Best family SUV", rounds_per_segment=3)
    for _ in range(3):
        state.increment_round()
    assert state.should_pause() is True

def test_should_not_pause_before_max_rounds():
    state = DebateState(topic="Best family SUV", rounds_per_segment=3)
    state.increment_round()
    assert state.should_pause() is False

def test_transition_to_final():
    state = DebateState(topic="Best family SUV")
    state.set_phase(DebatePhase.FINAL)
    assert state.phase == DebatePhase.FINAL

def test_add_user_info():
    state = DebateState(topic="Best family SUV")
    state.add_user_info("Family of 4, budget $40k")
    assert "Family of 4" in state.user_info[0]
