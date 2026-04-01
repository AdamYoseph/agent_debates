# orchestrator.py
from queue import Queue

from debate import DebatePhase, DebateState
from agent import parse_final_answer
from logging_utils import setup_logging
from protocol import Message, Signal
from search_tools import pre_search


def format_final_results(results: dict) -> str:
    all_agree = len(set(r["recommendation"] for r in results.values())) == 1 and all(
        r["consensus"] for r in results.values()
    )
    lines = ["\n" + "=" * 60, "FINAL RECOMMENDATIONS", "=" * 60]

    if all_agree:
        rec = list(results.values())[0]
        lines.append(f"\n✅ CONSENSUS REACHED: {rec['recommendation']}")
        lines.append(f"\nBoth agents agree: {rec['reason']}")
    else:
        lines.append("\n⚖️  No consensus — here are both picks:\n")
        for name, rec in results.items():
            lines.append(f"  {name}: {rec['recommendation']}")
            lines.append(f"    Reason: {rec['reason']}\n")
        lines.append("The final decision is yours!")

    # Consolidated runner-ups: merge, deduplicate, exclude winner(s), cap at 10
    winner_names = {r["recommendation"].lower() for r in results.values()}
    seen: set[str] = set()
    runner_ups: list[dict] = []
    for rec in results.values():
        for ru in rec.get("runner_ups", []):
            key = ru["name"].lower()
            if key not in seen and key not in winner_names:
                seen.add(key)
                runner_ups.append(ru)
                if len(runner_ups) >= 10:
                    break
        if len(runner_ups) >= 10:
            break

    if runner_ups:
        lines.append("\nWhy not the others:")
        for ru in runner_ups:
            lines.append(f"  • {ru['name']} — {ru['reason']}")

    lines.append("=" * 60)
    return "\n".join(lines)


def get_topic() -> str:
    print("\n=== Agent Debates ===")
    print("What topic should the agents debate?")
    return input("> ").strip()


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
