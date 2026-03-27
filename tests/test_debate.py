# tests/test_debate.py
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


def test_research_brief_default_empty():
    state = DebateState(topic="Best family SUV")
    assert state.research_brief == ""


def test_build_context_includes_research_brief():
    state = DebateState(topic="Best family SUV", research_brief="Toyota costs $30k")
    context = state.build_context()
    assert "Toyota costs $30k" in context
    assert "RESEARCH BRIEF" in context


def test_build_context_omits_brief_when_empty():
    state = DebateState(topic="Best family SUV")
    context = state.build_context()
    assert "RESEARCH BRIEF" not in context


def test_agent_motivations_default_empty():
    state = DebateState(topic="Best family SUV")
    assert state.agent_motivations == {}


def test_guidance_default_empty():
    state = DebateState(topic="Best family SUV")
    assert state.guidance == ""


def test_build_context_includes_agent_motivation():
    state = DebateState(
        topic="Best family SUV",
        agent_motivations={"Alpha": "comfort focused"},
    )
    context = state.build_context(agent_name="Alpha")
    assert "YOUR ROLE: comfort focused" in context


def test_build_context_omits_motivation_for_other_agent():
    state = DebateState(
        topic="Best family SUV",
        agent_motivations={"Alpha": "comfort focused"},
    )
    context = state.build_context(agent_name="Beta")
    assert "YOUR ROLE" not in context


def test_build_context_omits_motivation_when_no_agent_name():
    state = DebateState(
        topic="Best family SUV",
        agent_motivations={"Alpha": "comfort focused"},
    )
    context = state.build_context()
    assert "YOUR ROLE" not in context


def test_build_context_includes_guidance():
    state = DebateState(topic="Best family SUV", guidance="Budget max 200k ILS")
    context = state.build_context()
    assert "Budget max 200k ILS" in context
    assert "DEBATE GUIDANCE" in context


def test_build_context_omits_guidance_when_empty():
    state = DebateState(topic="Best family SUV")
    context = state.build_context()
    assert "DEBATE GUIDANCE" not in context


def test_build_context_with_motivation_and_guidance_together():
    state = DebateState(
        topic="Best family SUV",
        agent_motivations={"Alpha": "comfort focused"},
        guidance="Budget max 200k ILS",
    )
    context = state.build_context(agent_name="Alpha")
    assert "YOUR ROLE: comfort focused" in context
    assert "DEBATE GUIDANCE" in context
    assert "Budget max 200k ILS" in context
    # Role must appear before guidance
    assert context.index("YOUR ROLE") < context.index("DEBATE GUIDANCE")


def test_build_context_no_agent_name_still_shows_guidance():
    state = DebateState(
        topic="Best family SUV",
        agent_motivations={"Alpha": "comfort focused"},
        guidance="Budget max 200k ILS",
    )
    context = state.build_context()
    assert "YOUR ROLE" not in context
    assert "DEBATE GUIDANCE" in context
    assert "Budget max 200k ILS" in context


def test_build_context_respond_to_opponent_latest_message():
    state = DebateState(topic="Best family SUV")
    state.add_message("Alpha", "I think the Tucson is best.")
    state.add_message("Beta", "The RAV4 beats it on reliability.")
    state.add_message("Alpha", "But Tucson has better warranty coverage.")

    context = state.build_context(agent_name="Beta", opponent_name="Alpha")

    assert "RESPOND TO Alpha" in context
    assert "Tucson has better warranty coverage" in context


def test_build_context_respond_to_uses_most_recent_opponent_message():
    state = DebateState(topic="Best family SUV")
    state.add_message("Alpha", "First argument.")
    state.add_message("Beta", "Counter.")
    state.add_message("Alpha", "Second argument.")

    context = state.build_context(agent_name="Beta", opponent_name="Alpha")

    # Extract just the RESPOND TO section (between "RESPOND TO" and "TOPIC:")
    respond_to_section = context.split("RESPOND TO")[1].split("TOPIC:")[0]
    assert "Second argument" in respond_to_section
    assert "First argument" not in respond_to_section


def test_build_context_respond_to_appears_before_topic():
    state = DebateState(topic="Best family SUV")
    state.add_message("Alpha", "I think the Tucson is best.")

    context = state.build_context(agent_name="Beta", opponent_name="Alpha")

    assert context.index("RESPOND TO") < context.index("TOPIC:")


def test_build_context_no_respond_to_when_no_opponent_history():
    state = DebateState(topic="Best family SUV")
    context = state.build_context(agent_name="Beta", opponent_name="Alpha")

    assert "RESPOND TO" not in context


def test_build_context_no_respond_to_without_opponent_name():
    state = DebateState(topic="Best family SUV")
    state.add_message("Alpha", "I think the Tucson is best.")

    context = state.build_context(agent_name="Beta")

    assert "RESPOND TO" not in context
