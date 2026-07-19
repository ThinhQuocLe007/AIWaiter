"""Base types for long-conversation scenarios."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Turn:
    text: str
    note: str
    expected_intent: str


@dataclass
class Conversation:
    name: str
    table_id: str
    party_size: int
    turns: list[Turn]

    def __iter__(self):
        return iter(self.turns)

    def __len__(self) -> int:
        return len(self.turns)
