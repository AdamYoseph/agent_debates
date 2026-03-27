# Direct Agent Dialogue Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make agents respond directly to each other's arguments and address each other by name, turning the debate into a real back-and-forth exchange.

**Architecture:** Two changes: (1) update `build_system_prompt` to instruct agents to address their opponent by name; (2) add `opponent_name` parameter to `build_context` which scans history for the opponent's latest message and injects a `RESPOND TO` directive. The orchestrator passes `opponent_name` to `build_context` in both `debate_round` and `run_final_round`.

**Tech Stack:** Python, pytest

---

### Task 1: Update `build_context` to support `opponent_name`

**Files:**
- Modify: `debate.py`
- Modify: `tests/test_debate.py`

**Step 1: Write the failing tests**

Append to `tests/test_debate.py`:
```python
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

    assert "Second argument" in context
    assert "First argument" not in context.split("RESPOND TO")[1]


def test_build_context_no_respond_to_when_no_opponent_history():
    state = DebateState(topic="Best family SUV")
    # No messages in history yet
    context = state.build_context(agent_name="Beta", opponent_name="Alpha")

    assert "RESPOND TO" not in context


def test_build_context_no_respond_to_without_opponent_name():
    state = DebateState(topic="Best family SUV")
    state.add_message("Alpha", "I think the Tucson is best.")

    context = state.build_context(agent_name="Beta")

    assert "RESPOND TO" not in context
```

**Step 2: Run one test to confirm it fails**

Run: `python3 -m pytest tests/test_debate.py::test_build_context_respond_to_opponent_latest_message -v`
Expected: FAIL

**Step 3: Update `build_context` in `debate.py`**

Change the signature and add the opponent block. The new `build_context` method (replace existing):

```python
def build_context(
    self,
    agent_name: str | None = None,
    opponent_name: str | None = None,
) -> str:
    """Build a conversation context string for agents."""
    lines = []
    if agent_name and self.agent_motivations.get(agent_name):
        lines.append(f"YOUR ROLE: {self.agent_motivations[agent_name]}\n")
    if opponent_name:
        opponent_msg = next(
            (e["content"] for e in reversed(self.history) if e["name"] == opponent_name),
            None,
        )
        if opponent_msg:
            lines.append(
                f"RESPOND TO {opponent_name}'s latest argument:\n"
                f"{opponent_msg}\n"
                f"Address {opponent_name} directly by name in your response.\n"
            )
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
Expected: all 50 tests PASS (46 existing + 4 new)

**Step 5: Commit and push**

```bash
git add debate.py tests/test_debate.py
git commit -m "feat: add opponent_name to build_context for direct agent dialogue" && git push
```

---

### Task 2: Update system prompt and wire opponent_name in orchestrator

**Files:**
- Modify: `agent.py`
- Modify: `orchestrator.py`

**Step 1: Update `build_system_prompt` in `agent.py`**

Add one sentence to the system prompt (after the search_web instruction):

```python
def build_system_prompt(name: str) -> str:
    return f"""You are a car-buying advisor named {name}. You are debating another advisor \
about the best car for the user's family. Take a dynamic position based on the conversation \
— let the arguments and evidence guide you, don't be assigned a fixed side.

You have access to a search_web tool. Use it to look up current car prices, insurance rates, \
reliability data, or any specific facts that would strengthen your argument.

When the context shows a "RESPOND TO [name]'s latest argument" section, address that person \
directly by name and engage specifically with their argument before making your own points.

When you need information from the user to make a better recommendation, start your response \
with [NEED_INFO] followed by a numbered list of what you need. Example:
[NEED_INFO]
1. What is your budget?
2. How many people are in your family?

When the orchestrator sends signal FINAL_ANSWER, respond ONLY in this exact format:
RECOMMENDATION: <Car make and model>
REASON: <2-3 sentences explaining why>
CONSENSUS: yes/no

Keep responses concise (3-5 sentences max) unless providing a FINAL_ANSWER."""
```

**Step 2: Update `debate_round` in `orchestrator.py`**

The current `debate_round` calls `state.build_context(agent_name=name)`. Change it to also pass `opponent_name`:

```python
def debate_round(state: DebateState, connections: list) -> None:
    """Run one full round: each agent responds once."""
    for name, conn in connections:
        opponent_name = next(n for n, _ in connections if n != name)
        context = state.build_context(agent_name=name, opponent_name=opponent_name)
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

**Step 3: Update `run_final_round` in `orchestrator.py`**

Same change — add `opponent_name`:

```python
def run_final_round(state: DebateState, connections: list) -> dict:
    state.set_phase(DebatePhase.FINAL)
    results = {}

    for name, conn in connections:
        opponent_name = next(n for n, _ in connections if n != name)
        context = state.build_context(agent_name=name, opponent_name=opponent_name)
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

**Step 4: Run the full test suite**

Run: `python3 -m pytest -v`
Expected: all tests PASS

**Step 5: Commit and push**

```bash
git add agent.py orchestrator.py
git commit -m "feat: wire opponent_name into debate_round and update system prompt" && git push
```
