"""
Boundary state of the target object.

Originating module: Module 04 — Boundary Detection
Consuming module:   Module 05 — Perception Fusion (boundary / contact evidence)

Rotation is measured relative to the rack/payload reference, not camera "up".
These are evidence states only; Module 04 never decides procedure correctness.
"""

from enum import Enum


class BoundaryState(str, Enum):
    """Temporal state of the target object's boundary."""

    UNKNOWN = "unknown"          # insufficient / unconfirmed evidence
    STATIONARY = "stationary"    # boundary unchanged within configured tolerance
    MOVING = "moving"            # boundary translating
    ROTATING = "rotating"        # boundary rotating relative to the rack reference
    CONTACT = "contact"          # hand boundary in contact with object boundary
    SEPARATING = "separating"    # hand / object boundaries moving apart after contact
