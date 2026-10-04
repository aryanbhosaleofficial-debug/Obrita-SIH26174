"""
Hand-object interaction state.

Originating module: Module 03 — Optimization Sequence (Teammate 4, interaction/)
Consuming module:   Module 04 (target selection, cross-check), Module 05 (interaction evidence)

These are perception states only. They do not say whether a procedure step
was performed correctly; that is decided by the Procedure FSM.
"""

from enum import Enum


class InteractionState(str, Enum):
    """Interaction between one hand and one object track."""

    UNKNOWN = "unknown"            # not enough evidence (e.g. hand not visible)
    NONE = "none"                  # hand clearly not interacting with the object
    APPROACHING = "approaching"    # hand moving towards the object
    NEAR = "near"                  # hand within the configured proximity threshold
    TOUCHING = "touching"          # hand overlaps / touches the object (image evidence)
    MANIPULATING = "manipulating"  # touching while the object moves with the hand
    RELEASING = "releasing"        # hand moving away after touching
