# debate.py
from dataclasses import dataclass, field
from enum import Enum
from typing import List
from config import Config


class DebatePhase(Enum):
    DEBATING = "debating"
    PAUSED = "paused"
    FINAL = "final"
    DONE = "done"


@dataclass
class DebateState:
    topic: str
    rounds_per_segment: int = Config.ROUNDS_PER_SEGMENT
    phase: DebatePhase = DebatePhase.DEBATING
    round: int = 0
    history: List[dict] = field(default_factory=list)
    user_info: List[str] = field(default_factory=list)

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

    def build_context(self) -> str:
        """Build a conversation context string for agents."""
        lines = [f"TOPIC: {self.topic}"]
        if self.user_info:
            lines.append("\nUSER INFO PROVIDED:")
            for info in self.user_info:
                lines.append(f"  - {info}")
        lines.append("\nDEBATE HISTORY:")
        for entry in self.history:
            lines.append(f"  {entry['name']}: {entry['content']}")
        return "\n".join(lines)
