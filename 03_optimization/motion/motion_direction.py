"""
Motion direction.

Implementation status:
    Scaffold only.

Input:
    Velocity vectors

Output:
    Direction relative to rack axes

Owner:
    Module 03 — Optimization Sequence (Teammate 4: temporal section)
"""

import math

def direction(vector, deadband=1e-6):
    x,y=vector
    if math.hypot(x,y)<=deadband: return "STATIONARY"
    if abs(x)>deadband and abs(y)>deadband: return ("DOWN" if y>0 else "UP")+"_"+("RIGHT" if x>0 else "LEFT")
    return ("RIGHT" if x>0 else "LEFT") if abs(x)>=abs(y) else ("DOWN" if y>0 else "UP")
