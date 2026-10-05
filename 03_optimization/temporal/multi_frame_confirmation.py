"""Consecutive confirmation with latched short-gap tolerance and EMA confidence."""

from dataclasses import dataclass


@dataclass
class Confirmation:
    hits: int = 0
    missing: int = 0
    confirmed: bool = False
    score: float | None = None
    consecutive_seen: int = 0

    def observe(self, score: float | None, minimum: int, alpha: float) -> None:
        self.hits += 1
        self.consecutive_seen += 1
        self.missing = 0
        self.confirmed = self.confirmed or self.hits >= minimum
        if score is not None:
            self.score = (
                score
                if self.score is None
                else alpha * score + (1 - alpha) * self.score
            )

    def miss(self) -> None:
        self.missing += 1
        self.consecutive_seen = 0
        if not self.confirmed:
            self.hits = 0
            self.score = None
