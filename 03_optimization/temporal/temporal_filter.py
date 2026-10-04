"""
Temporal filtering (debounce / hysteresis).

Implementation status:
    Scaffold only.

Input:
    Per-frame labels/states

Output:
    Debounced labels/states

Owner:
    Module 03 — Optimization Sequence (Teammate 4: temporal section)
"""

from collections import Counter, deque

class HysteresisFilter:
    def __init__(self, window=3): self.window=deque(maxlen=max(1,int(window))); self.current="UNKNOWN"
    def update(self,label):
        self.window.append(label); candidate,count=Counter(self.window).most_common(1)[0]
        if count >= 2 or len(self.window)==1: self.current=candidate
        return self.current
