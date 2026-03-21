# protocol.py
import json
from dataclasses import dataclass, asdict
from typing import Optional


class Signal:
    NEED_INFO = "NEED_INFO"
    FINAL_ANSWER = "FINAL_ANSWER"


@dataclass
class Message:
    role: str
    name: str
    content: str
    signal: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "Message":
        parsed = json.loads(data)
        return cls(**parsed)
