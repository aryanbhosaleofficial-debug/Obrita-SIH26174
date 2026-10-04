"""
Velocity estimation.

Implementation status:
    Scaffold only.

Input:
    Displacements + timestamp_s

Output:
    Velocity (rack-relative units per second)

Owner:
    Module 03 — Optimization Sequence (Teammate 4: temporal section)
"""

def velocity(previous, current, previous_timestamp, current_timestamp):
    dt = float(current_timestamp) - float(previous_timestamp)
    if dt <= 0: return (0.0, 0.0)
    return ((float(current[0])-float(previous[0]))/dt, (float(current[1])-float(previous[1]))/dt)

calculate_velocity = velocity
