# agent.py
import socket
import argparse
import re
from anthropic import Anthropic
from config import Config
from protocol import Message, Signal
from socket_utils import send_message, recv_message


def build_system_prompt(name: str) -> str:
    return f"""You are a car-buying advisor named {name}. You are debating another advisor \
about the best car for the user's family. Take a dynamic position based on the conversation \
— let the arguments and evidence guide you, don't be assigned a fixed side.

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


def parse_final_answer(response: str) -> dict:
    rec_match = re.search(r"RECOMMENDATION:\s*(.+)", response)
    reason_match = re.search(r"REASON:\s*(.+)", response)
    consensus_match = re.search(r"CONSENSUS:\s*(yes|no)", response, re.IGNORECASE)

    return {
        "recommendation": rec_match.group(1).strip() if rec_match else "",
        "reason": reason_match.group(1).strip() if reason_match else "",
        "consensus": consensus_match.group(1).lower() == "yes" if consensus_match else False,
    }


def run_agent(name: str):
    client = Anthropic()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((Config.HOST, Config.PORT))
    print(f"[{name}] Connected to orchestrator.")

    conversation = []

    while True:
        msg = recv_message(sock)

        if msg.signal == Signal.FINAL_ANSWER:
            print(f"\n[{name}] Generating final recommendation...")
            conversation.append({"role": "user", "content": msg.content + "\n\nProvide your FINAL_ANSWER now."})
        else:
            print(f"\n[{name}] Received: {msg.content[:80]}...")
            conversation.append({"role": "user", "content": msg.content})

        response = client.messages.create(
            model=Config.MODEL,
            max_tokens=Config.MAX_TOKENS,
            system=build_system_prompt(name),
            messages=conversation,
        )
        reply = response.content[0].text
        conversation.append({"role": "assistant", "content": reply})

        print(f"\n[{name}] My response:\n{reply}\n")

        signal = None
        if reply.strip().startswith("[NEED_INFO]"):
            signal = Signal.NEED_INFO

        out = Message(role="agent", name=name, content=reply, signal=signal)
        send_message(sock, out)

        if msg.signal == Signal.FINAL_ANSWER:
            break

    sock.close()
    print(f"[{name}] Debate complete. Disconnecting.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Agent name (e.g. Alpha or Beta)")
    args = parser.parse_args()
    run_agent(args.name)
