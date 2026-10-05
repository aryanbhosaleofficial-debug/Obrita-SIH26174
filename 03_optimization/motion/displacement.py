"""
Landmark / hand displacement between frames.

Implementation status:
    Scaffold only.

Input:
    Rack-relative landmarks over a window

Output:
    Displacement vectors (rack-relative units)

Owner:
    Module 03 — Optimization Sequence (Teammate 4: temporal section)
"""

def displacement(previous, current):
    if previous is None or current is None: return (0.0, 0.0)
    return (float(current[0])-float(previous[0]), float(current[1])-float(previous[1]))
