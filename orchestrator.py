# orchestrator.py
import socket
import argparse
from config import Config
from protocol import Message, Signal
from socket_utils import send_message, recv_message
from debate import DebateState, DebatePhase
from agent import parse_final_answer
from search_tools import pre_search
from logging_utils import setup_logging


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

    lines.append("=" * 60)
    return "\n".join(lines)


def get_topic(args) -> str:
    if args.topic:
        return args.topic
    print("\n=== Agent Debates ===")
    print("What topic should the agents debate?")
    return input("> ").strip()


def collect_agents(server_sock: socket.socket, count: int = 2) -> list:
    connections = []
    print(f"\nWaiting for {count} agents to connect on port {Config.PORT}...")
    while len(connections) < count:
        conn, addr = server_sock.accept()
        # Receive agent registration message
        msg = recv_message(conn)
        print(f"  Agent '{msg.name}' connected from {addr}")
        connections.append((msg.name, conn))
    return connections


def collect_debate_setup(connections: list) -> tuple[dict, str]:
    """Prompt user for per-agent motivations and optional guidance."""
    print("\n=== Debate Setup ===")
    agent_motivations = {}
    for name, _ in connections:
        motivation = input(
            f"{name}'s motivation? (e.g. 'comfort focused', leave blank to skip)\n> "
        ).strip()
        if motivation:
            agent_motivations[name] = motivation

    guidance = input(
        "\nDebate guidance/constraints? (e.g. 'budget 150-250k ILS', leave blank to skip)\n> "
    ).strip()

    return agent_motivations, guidance


def broadcast(connections: list, msg: Message) -> None:
    for _, conn in connections:
        send_message(conn, msg)


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
            # Extract the NEED_INFO content and ask user
            info_request = reply.content.replace("[NEED_INFO]", "").strip()
            print(f"\n[{name} needs more info from you]:\n{info_request}")
            print("\nYour answer:")
            user_answer = input("> ").strip()
            state.add_user_info(f"Re: {name}'s question — {user_answer}")
            # Acknowledge and continue
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


def run_debate(topic: str) -> None:
    logger = setup_logging("orchestrator")
    logger.info(f"Debate topic: {topic}")

    print(f"\nResearching '{topic}'...")
    brief = pre_search(topic)
    logger.info("Pre-search complete")

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((Config.HOST, Config.PORT))
    server_sock.listen(2)

    connections = collect_agents(server_sock)
    logger.info(f"Agents connected: {[name for name, _ in connections]}")
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

    for _, conn in connections:
        conn.close()
    server_sock.close()
    logger.info("Debate complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Debates Orchestrator")
    parser.add_argument(
        "--topic", type=str, default="", help="Debate topic (prompted if omitted)"
    )
    args = parser.parse_args()

    topic = get_topic(args)
    run_debate(topic)
