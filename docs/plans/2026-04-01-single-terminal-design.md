# Single-Terminal Execution Design

**Date:** 2026-04-01
**Status:** Approved

## Goal

Run the entire debate system from one terminal. Orchestrator and both agents run as threads in the same process, communicating via in-process queues instead of TCP sockets.

## Approach

Queue-based threading (Approach A). Replace the socket transport layer with `queue.Queue` pairs — one inbox and one outbox per agent. Keep all existing business logic, message types, and debate state unchanged.

## Section 1: Architecture

`main.py` is the single entry point. It creates four queues, starts three threads, and waits for completion.

```
main.py
├── alpha_inbox, alpha_outbox = Queue(), Queue()
├── beta_inbox,  beta_outbox  = Queue(), Queue()
├── Thread: run_debate(topic, alpha_inbox, alpha_outbox, beta_inbox, beta_outbox)
├── Thread: run_agent("Alpha", alpha_inbox, alpha_outbox)
└── Thread: run_agent("Beta",  beta_inbox,  beta_outbox)
```

From the orchestrator's perspective: agent inbox = where orchestrator writes; agent outbox = where orchestrator reads.

`socket_utils.py` is deleted. `protocol.py`, `debate.py`, `search_tools.py`, `logging_utils.py`, and `config.py` are untouched.

## Section 2: Changes to `agent.py`

- `run_agent(name)` → `run_agent(name, inbox, outbox)`
- `recv_message(sock)` → `inbox.get()` (blocks until orchestrator sends)
- `send_message(sock, msg)` → `outbox.put(msg)`
- Remove all socket imports and setup
- Remove `if __name__ == "__main__"` argparse block

All other logic (quota retry, tool calls, NEED_INFO, FINAL_ANSWER) unchanged.

## Section 3: Changes to `orchestrator.py`

- `run_debate(topic)` → `run_debate(topic, alpha_inbox, alpha_outbox, beta_inbox, beta_outbox)`
- Internal connections: `(name, socket)` pairs → `(name, inbox, outbox)` tuples
- `send_message(conn, msg)` → `inbox.put(msg)`
- `recv_message(conn)` → `outbox.get()`
- Delete `collect_agents` (no more TCP server setup)
- Remove `if __name__ == "__main__"` block

Everything else (`debate_round`, `run_final_round`, `collect_debate_setup`, `format_final_results`) unchanged.

## Section 4: `main.py`

New file. Topic collection runs on the main thread before starting threads.

```python
from queue import Queue
from threading import Thread
from agent import run_agent
from orchestrator import run_debate, get_topic

topic = get_topic()

alpha_inbox, alpha_outbox = Queue(), Queue()
beta_inbox,  beta_outbox  = Queue(), Queue()

threads = [
    Thread(target=run_debate, args=(topic, alpha_inbox, alpha_outbox, beta_inbox, beta_outbox)),
    Thread(target=run_agent,  args=("Alpha", alpha_inbox, alpha_outbox)),
    Thread(target=run_agent,  args=("Beta",  beta_inbox,  beta_outbox)),
]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

## Section 5: Tests

- Delete `test_socket_utils.py` (socket_utils.py is removed)
- All other test files unchanged — none test socket I/O directly
- `protocol.py` and `Message`/`Signal` types are kept (still used as typed message containers through queues)

## Files Changed

- Create: `main.py`
- Modify: `agent.py`
- Modify: `orchestrator.py`
- Delete: `socket_utils.py`
- Delete: `tests/test_socket_utils.py`
