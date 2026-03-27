# Agent Motivations & Debate Guidance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users set a unique motivation per agent (e.g. "comfort focused") and an optional debate guidance block (e.g. "budget 150–250k ILS") interactively at orchestrator startup, injected into every context message.

**Architecture:** Two new fields on `DebateState` (`agent_motivations: dict`, `guidance: str`). `build_context(agent_name=None)` personalizes per agent. A new `collect_debate_setup(connections)` function in the orchestrator prompts the user after agents connect. `debate_round` passes `agent_name` to `build_context`.

**Tech Stack:** Python dataclasses, pytest

---

### Task 1: Add `agent_motivations` and `guidance` to `DebateState`

**Files:**
- Modify: `debate.py`
- Modify: `tests/test_debate.py`

**Step 1: Write the failing tests**

Append to `tests/test_debate.py`:
```python
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
```

**Step 2: Run tests to confirm they fail**

Run: `python3 -m pytest tests/test_debate.py::test_agent_motivations_default_empty -v`
Expected: FAIL with `TypeError: unexpected keyword argument 'agent_motivations'`

**Step 3: Update `debate.py`**

Replace the entire `DebateState` dataclass with:
```python
@dataclass
class DebateState:
    topic: str
    rounds_per_segment: int = Config.ROUNDS_PER_SEGMENT
    phase: DebatePhase = DebatePhase.DEBATING
    round: int = 0
    history: List[dict] = field(default_factory=list)
    user_info: List[str] = field(default_factory=list)
    research_brief: str = ""
    agent_motivations: dict = field(default_factory=dict)
    guidance: str = ""

    def add_message(self, name: str, content: str) -> None:
        self.history.append({"name": name, "content": content})

    def add_user_info(self, info: str) -> None:
        self.user_info.append(info)

    def increment_round(self) -> None:
        self.round += 1

    def should_pause(self) -> bool:
        return self.round >= self.rounds_per_segment

    def set_phase(self, phase: DebatePhase) -> None:
        self.phase = phase

    def reset_round_counter(self) -> None:
        self.round = 0

    def build_context(self, agent_name: str = None) -> str:
        """Build a conversation context string for agents."""
        lines = []
        if agent_name and agent_name in self.agent_motivations:
            lines.append(f"YOUR ROLE: {self.agent_motivations[agent_name]}\n")
        lines.append(f"TOPIC: {self.topic}")
        if self.research_brief:
            lines.append(f"\nRESEARCH BRIEF:\n{self.research_brief}")
        if self.guidance:
            lines.append(f"\nDEBATE GUIDANCE:\n{self.guidance}")
        if self.user_info:
            lines.append("\nUSER INFO PROVIDED:")
            for info in self.user_info:
                lines.append(f"  - {info}")
        lines.append("\nDEBATE HISTORY:")
        for entry in self.history:
            lines.append(f"  {entry['name']}: {entry['content']}")
        return "\n".join(lines)
```

**Step 4: Run all debate tests**

Run: `python3 -m pytest tests/test_debate.py -v`
Expected: 17 tests PASS

**Step 5: Commit**

```bash
git add debate.py tests/test_debate.py
git commit -m "feat: add agent_motivations and guidance to DebateState" && git push
```

---

### Task 2: Add `collect_debate_setup` and wire into orchestrator

**Files:**
- Modify: `orchestrator.py`

**Step 1: Add `collect_debate_setup` function**

Add this function to `orchestrator.py` after `collect_agents`:

```python
def collect_debate_setup(connections: list) -> tuple:
    """Prompt user for per-agent motivations and optional guidance."""
    print("\n=== Debate Setup ===")
    agent_motivations = {}
    for name, _ in connections:
        motivation = input(f"{name}'s motivation? (e.g. 'comfort focused', leave blank to skip)\n> ").strip()
        if motivation:
            agent_motivations[name] = motivation

    guidance = input(
        "\nDebate guidance/constraints? (e.g. 'budget 150-250k ILS', leave blank to skip)\n> "
    ).strip()

    return agent_motivations, guidance
```

**Step 2: Update `run_debate` to call it**

In `run_debate`, after `connections = collect_agents(server_sock)`, add:

```python
agent_motivations, guidance = collect_debate_setup(connections)
```

And update the `DebateState` construction:

```python
state = DebateState(
    topic=topic,
    research_brief=brief,
    agent_motivations=agent_motivations,
    guidance=guidance,
)
```

**Step 3: Update `debate_round` to pass `agent_name`**

In `debate_round`, change:
```python
context = state.build_context()
```
to:
```python
context = state.build_context(agent_name=name)
```

Note: this line is inside the `for name, conn in connections:` loop, so `name` is already available. Move the `build_context` call inside the loop if it isn't already.

Current `debate_round` calls `build_context()` once before the loop. Change it to call per-agent inside the loop:

```python
def debate_round(state: DebateState, connections: list) -> None:
    """Run one full round: each agent responds once."""
    for name, conn in connections:
        context = state.build_context(agent_name=name)
        prompt = Message(
            role="orchestrator", name="Orchestrator", content=context, signal=None
        )
        send_message(conn, prompt)

        reply = recv_message(conn)
        print(f"\n--- {reply.name} ---\n{reply.content}\n")

        if reply.signal == Signal.NEED_INFO:
            info_request = reply.content.replace("[NEED_INFO]", "").strip()
            print(f"\n[{name} needs more info from you]:\n{info_request}")
            print("\nYour answer:")
            user_answer = input("> ").strip()
            state.add_user_info(f"Re: {name}'s question — {user_answer}")
            ack = Message(
                role="orchestrator",
                name="Orchestrator",
                content=f"User provided: {user_answer}. Please continue your argument.",
                signal=None,
            )
            send_message(conn, ack)
            reply = recv_message(conn)
            print(f"\n--- {reply.name} (continued) ---\n{reply.content}\n")

        state.add_message(reply.name, reply.content)

    state.increment_round()
```

Also update `run_final_round` to pass `agent_name`:
```python
def run_final_round(state: DebateState, connections: list) -> dict:
    state.set_phase(DebatePhase.FINAL)
    results = {}

    for name, conn in connections:
        context = state.build_context(agent_name=name)
        msg = Message(
            role="orchestrator",
            name="Orchestrator",
            content=context,
            signal=Signal.FINAL_ANSWER,
        )
        send_message(conn, msg)
        reply = recv_message(conn)
        print(f"\n--- {reply.name} FINAL ---\n{reply.content}\n")
        results[name] = parse_final_answer(reply.content)

    return results
```

**Step 4: Run full test suite**

Run: `python3 -m pytest -v`
Expected: all tests PASS

**Step 5: Commit**

```bash
git add orchestrator.py
git commit -m "feat: add collect_debate_setup and per-agent context in debate_round" && git push
```
