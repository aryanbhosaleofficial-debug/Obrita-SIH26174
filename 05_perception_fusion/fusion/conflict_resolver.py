"""Record disagreement; optionally defer to quality-gated confirmed boundary."""


def resolve(evidence, boundary, config):
    evidence = dict(evidence)
    conflicts = []
    motion = evidence.get("motion", (None, None))[0]
    state = evidence.get("boundary", (None, None))[0]
    opposite_motion = (motion, state) in (("moving", "stationary"), ("stationary", "moving"))
    if boundary is not None and boundary.quality_ok and boundary.state_confirmed and (boundary.crosscheck_agrees is False or opposite_motion):
        conflicts = ["Module 03 and confirmed Module 04 evidence disagree"]
        if config["policy"] == "mark_uncertain":
            evidence.clear()
        else:
            evidence.pop("interaction", None)
            evidence.pop("motion", None)
    return evidence, conflicts if config["record_conflicts"] else []
