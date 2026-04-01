# Single-Terminal Execution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace TCP socket communication with in-process `queue.Queue` pairs so the entire debate system runs from one terminal with a single `python3 main.py` command.

**Architecture:** Three threads (orchestrator, Alpha, Beta) run in one process. Each agent gets an inbox queue (orchestrator → agent) and outbox queue (agent → orchestrator). `socket_utils.py` is deleted. All other business logic is unchanged.

**Tech Stack:** Python 3 stdlib `queue.Queue`, `threading.Thread`. No new dependencies.

---

### Task 1: Refactor `agent.py` — replace sockets with queue parameters

**Files:**
- Modify: `agent.py`
- Test: `tests/test_agent.py` (existing tests must still pass — no new tests needed)

**Step 1: Update imports in `agent.py`**

Remove `socket`, `argparse`, and `socket_utils` from the top of the file. The new import block:

```python
# agent.py
import os
import time
import re
from queue import Queue
from google import genai
from google.genai import types
from config import Config
from protocol import Message, Signal
from search_tools import search_web, SEARCH_TOOL_DEFINITION
from logging_utils import setup_logging
```

**Step 2: Replace `run_agent` with queue-based version**

Replace the entire `run_agent` function and remove the `if __name__ == "__main__"` block at the bottom. New function:

```python
def run_agent(name: str, inbox: Queue, outbox: Queue) -> None:
    logger = setup_logging(f"agent-{name}")
    logger.info(f"Agent {name} starting")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    tool = types.Tool(function_declarations=[SEARCH_TOOL_DEFINITION])

    chat = client.chats.create(
        model=Config.MODEL,
        config=types.GenerateContentConfig(
            system_instruction=build_system_prompt(name),
            max_output_tokens=Config.MAX_TOKENS,
            tools=[tool],
        ),
    )

    print(f"[{name}] Ready.")
    logger.info("Ready")

    while True:
        msg = inbox.get()

        if msg.signal == Signal.FINAL_ANSWER:
            print(f"\n[{name}] Generating final recommendation...")
            logger.info("Received FINAL_ANSWER signal")
            user_message = msg.content + "\n\nProvide your FINAL_ANSWER now."
        else:
            print(f"\n[{name}] Received: {msg.content[:80]}...")
            logger.info(f"Received message: {msg.content[:200]}")
            user_message = msg.content

        try:
            response = _gemini_call(chat.send_message, user_message, logger=logger)
            reply = handle_tool_calls(response, chat, logger=logger)
        except Exception as e:
            print(f"\n[{name}] ERROR calling Gemini API: {e}")
            logger.error(f"Gemini API error: {e}")
            raise

        print(f"\n[{name}] My response:\n{reply}\n")
        logger.info(f"Response: {reply}")

        signal = None
        if reply.strip().startswith("[NEED_INFO]"):
            signal = Signal.NEED_INFO
            logger.info("Emitting NEED_INFO signal")

        out = Message(role="agent", name=name, content=reply, signal=signal)
        outbox.put(out)

        if msg.signal == Signal.FINAL_ANSWER:
            break

    logger.info("Debate complete.")
    print(f"[{name}] Debate complete.")
```

**Step 3: Run existing tests to verify nothing broke**

```bash
python3 -m pytest tests/test_agent.py -v
```

Expected: all 13 tests pass (they test `build_system_prompt`, `parse_final_answer`, `handle_tool_calls` — none touch `run_agent` directly).

**Step 4: Commit**

```bash
git add agent.py
git commit -m "refactor: replace socket I/O in agent with queue inbox/outbox"
```

---

### Task 2: Refactor `orchestrator.py` — replace sockets with queue parameters

**Files:**
- Modify: `orchestrator.py`
- Test: `tests/test_orchestrator.py` (existing tests must still pass — no new tests needed)

**Step 1: Update imports in `orchestrator.py`**

Remove `socket`, `argparse`, and `socket_utils`. New import block:

```python
# orchestrator.py
from queue import Queue
from config import Config
from protocol import Message, Signal
from debate import DebateState, DebatePhase
from agent import parse_final_answer
from search_tools import pre_search
from logging_utils import setup_logging
```

**Step 2: Update `get_topic` — remove argparse dependency**

Replace the existing `get_topic(args)` with a no-argument version:

```python
def get_topic() -> str:
    print("\n=== Agent Debates ===")
    print("What topic should the agents debate?")
    return input("> ").strip()
```

**Step 3: Delete `collect_agents` and `broadcast` functions entirely**

These functions use sockets and are not needed. Remove them completely.

**Step 4: Update `collect_debate_setup` — handle 3-tuple connections**

The `connections` list changes from `[(name, socket), ...]` to `[(name, inbox, outbox), ...]`. Update the iteration:

```python
def collect_debate_setup(connections: list) -> tuple[dict, str]:
    """Prompt user for per-agent motivations and optional guidance."""
    print("\n=== Debate Setup ===")
    agent_motivations = {}
    for name, *_ in connections:
        motivation = input(
            f"{name}'s motivation? (e.g. 'comfort focused', leave blank to skip)\n> "
        ).strip()
        if motivation:
            agent_motivations[name] = motivation

    guidance = input(
        "\nDebate guidance/constraints? (e.g. 'budget 150-250k ILS', leave blank to skip)\n> "
    ).strip()

    return agent_motivations, guidance
```

**Step 5: Update `debate_round` — replace send/recv with queue ops**

```python
def debate_round(state: DebateState, connections: list) -> None:
    """Run one full round: each agent responds once."""
    for name, inbox, outbox in connections:
        opponent_name = next(n for n, *_ in connections if n != name)
        context = state.build_context(agent_name=name, opponent_name=opponent_name)
        prompt = Message(
            role="orchestrator", name="Orchestrator", content=context, signal=None
        )
        inbox.put(prompt)

        reply = outbox.get()
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
            inbox.put(ack)
            reply = outbox.get()
            print(f"\n--- {reply.name} (continued) ---\n{reply.content}\n")

        state.add_message(reply.name, reply.content)

    state.increment_round()
```

**Step 6: Update `run_final_round` — replace send/recv with queue ops**

```python
def run_final_round(state: DebateState, connections: list) -> dict:
    state.set_phase(DebatePhase.FINAL)
    results = {}

    for name, inbox, outbox in connections:
        opponent_name = next(n for n, *_ in connections if n != name)
        context = state.build_context(agent_name=name, opponent_name=opponent_name)
        msg = Message(
            role="orchestrator",
            name="Orchestrator",
            content=context,
            signal=Signal.FINAL_ANSWER,
        )
        inbox.put(msg)
        reply = outbox.get()
        print(f"\n--- {reply.name} FINAL ---\n{reply.content}\n")
        results[name] = parse_final_answer(reply.content)

    return results
```

**Step 7: Update `run_debate` — remove TCP server, accept queues as parameters**

```python
def run_debate(
    topic: str,
    alpha_inbox: Queue,
    alpha_outbox: Queue,
    beta_inbox: Queue,
    beta_outbox: Queue,
) -> None:
    logger = setup_logging("orchestrator")
    logger.info(f"Debate topic: {topic}")

    print(f"\nResearching '{topic}'...")
    brief = pre_search(topic)
    logger.info("Pre-search complete")

    connections = [
        ("Alpha", alpha_inbox, alpha_outbox),
        ("Beta", beta_inbox, beta_outbox),
    ]
    logger.info(f"Agents: {[name for name, *_ in connections]}")
    agent_motivations, guidance = collect_debate_setup(connections)
    logger.info(f"Motivations: {agent_motivations}, Guidance: {guidance!r}")
    print(f"\n=== Debate starting: {topic} ===\n")

    state = DebateState(
        topic=topic,
        research_brief=brief,
        agent_motivations=agent_motivations,
        guidance=guidance,
    )

    while state.phase == DebatePhase.DEBATING:
        logger.info(f"Round {state.round + 1}")
        debate_round(state, connections)

        if state.should_pause():
            state.set_phase(DebatePhase.PAUSED)
            print("\n" + "-" * 40)
            print("Debate paused. Options:")
            print("  [q] Wrap up and get final recommendations")
            print("  [anything else] Ask a new question to continue the debate")
            choice = input("> ").strip()

            if choice.lower() == "q":
                logger.info("User chose to wrap up")
                break
            else:
                logger.info(f"User question: {choice}")
                state.add_message("User", choice)
                state.reset_round_counter()
                state.set_phase(DebatePhase.DEBATING)

    results = run_final_round(state, connections)
    final_output = format_final_results(results)
    print(final_output)
    logger.info(f"Final results: {results}")
    logger.info("Debate complete")
```

Also remove the `if __name__ == "__main__"` block at the bottom of the file.

**Step 8: Run existing orchestrator tests**

```bash
python3 -m pytest tests/test_orchestrator.py -v
```

Expected: all 6 tests pass (`format_final_results` tests — they don't touch sockets).

**Step 9: Commit**

```bash
git add orchestrator.py
git commit -m "refactor: replace socket I/O in orchestrator with queue inbox/outbox pairs"
```

---

### Task 3: Create `main.py`

**Files:**
- Create: `main.py`

**Step 1: Create the file**

```python
# main.py
from queue import Queue
from threading import Thread

from agent import run_agent
from orchestrator import get_topic, run_debate


def main() -> None:
    topic = get_topic()

    alpha_inbox: Queue = Queue()
    alpha_outbox: Queue = Queue()
    beta_inbox: Queue = Queue()
    beta_outbox: Queue = Queue()

    threads = [
        Thread(
            target=run_debate,
            args=(topic, alpha_inbox, alpha_outbox, beta_inbox, beta_outbox),
            name="Orchestrator",
        ),
        Thread(target=run_agent, args=("Alpha", alpha_inbox, alpha_outbox), name="Alpha"),
        Thread(target=run_agent, args=("Beta", beta_inbox, beta_outbox), name="Beta"),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
```

**Step 2: Run full test suite to verify nothing broke**

```bash
python3 -m pytest -v
```

Expected: all 61 tests pass.

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add main.py as single-terminal entry point"
```

---

### Task 4: Delete `socket_utils.py` and `tests/test_socket_utils.py`, final check, push

**Files:**
- Delete: `socket_utils.py`
- Delete: `tests/test_socket_utils.py`

**Step 1: Delete the files**

```bash
git rm socket_utils.py tests/test_socket_utils.py
```

**Step 2: Run full test suite**

```bash
python3 -m pytest -v
```

Expected: all remaining tests pass (9 fewer tests than before since `test_socket_utils.py` is gone).

**Step 3: Commit and push**

```bash
git commit -m "chore: remove socket_utils now that transport layer uses queues"
git push
```
