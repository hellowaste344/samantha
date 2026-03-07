"""
core/context.py — In-memory rolling conversation window.
Holds the last N turns so the planner has short-term context
without querying SQLite on every call.
"""
from __future__ import annotations
from collections import deque
from typing import List, Dict

import config


class Context:
    def __init__(self, max_turns: int = config.CONTEXT_WINDOW_SIZE):
        self._max   = max_turns
        self._turns: deque = deque(maxlen=max_turns)

    def add(self, role: str, content: str):
        """role must be 'user' or 'assistant'."""
        self._turns.append({"role": role, "content": content})

    def messages(self) -> List[Dict[str, str]]:
        """Return all stored turns as a plain list of dicts."""
        return list(self._turns)

    def as_text(self) -> str:
        lines = []
        for t in self._turns:
            label = "User" if t["role"] == "user" else "Samantha"
            lines.append(f"{label}: {t['content']}")
        return "\n".join(lines)

    def clear(self):
        self._turns.clear()

    def __len__(self) -> int:
        return len(self._turns)
