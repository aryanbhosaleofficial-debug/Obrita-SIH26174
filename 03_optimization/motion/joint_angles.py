"""
Joint angle computation.

Implementation status:
    Scaffold only.

Input:
    SpatialFeaturePacket landmarks

Output:
    Joint angles in degrees

Owner:
    Module 03 — Optimization Sequence (Teammate 4: temporal section)
"""

import math

def joint_angle(a, vertex, b):
    va=(a[0]-vertex[0], a[1]-vertex[1]); vb=(b[0]-vertex[0], b[1]-vertex[1])
    na=math.hypot(*va); nb=math.hypot(*vb)
    if not na or not nb: return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, (va[0]*vb[0]+va[1]*vb[1])/(na*nb)))))
