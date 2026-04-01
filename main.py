# main.py
import sys
from queue import Queue
from threading import Event, Thread

from agent import run_agent
from orchestrator import get_topic, run_debate


def _run_with_shutdown(fn, args, queues: list[Queue], error_event: Event) -> None:
    """Run fn(*args). On any exception, signal shutdown and unblock all queues."""
    try:
        fn(*args)
    except Exception as e:
        print(f"\n[ERROR] Thread {fn.__name__} failed: {e}", file=sys.stderr)
        error_event.set()
        for q in queues:
            q.put(None)  # unblock any thread blocked on q.get()


def main() -> None:
    topic = get_topic()

    alpha_inbox: Queue = Queue()
    alpha_outbox: Queue = Queue()
    beta_inbox: Queue = Queue()
    beta_outbox: Queue = Queue()
    all_queues = [alpha_inbox, alpha_outbox, beta_inbox, beta_outbox]

    error_event = Event()

    threads = [
        Thread(
            target=_run_with_shutdown,
            args=(
                run_debate,
                (topic, alpha_inbox, alpha_outbox, beta_inbox, beta_outbox),
                all_queues,
                error_event,
            ),
            name="Orchestrator",
        ),
        Thread(
            target=_run_with_shutdown,
            args=(
                run_agent,
                ("Alpha", alpha_inbox, alpha_outbox),
                all_queues,
                error_event,
            ),
            name="Alpha",
        ),
        Thread(
            target=_run_with_shutdown,
            args=(
                run_agent,
                ("Beta", beta_inbox, beta_outbox),
                all_queues,
                error_event,
            ),
            name="Beta",
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if error_event.is_set():
        sys.exit(1)


if __name__ == "__main__":
    main()
