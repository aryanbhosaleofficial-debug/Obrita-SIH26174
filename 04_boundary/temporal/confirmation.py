"""Bounded N-of-M confirmation of the current valid-frame candidate."""

from collections import deque

from shared.enums.boundary_state import BoundaryState


class StateConfirmation:
    def __init__(self, n=2, m=3):
        if type(n) is not int or type(m) is not int or not 1 <= n <= m:
            raise ValueError("confirmation requires integer 1 <= n <= m")
        self.n = n
        self.history = deque(maxlen=m)

    def reset(self):
        self.history.clear()

    def update(self, candidate: BoundaryState) -> tuple[BoundaryState, bool, int]:
        self.history.append(candidate)
        count = self.history.count(candidate)
        confirmed = candidate != BoundaryState.UNKNOWN and count >= self.n
        return (
            (candidate, True, count) if confirmed else (BoundaryState.UNKNOWN, False, 0)
        )
