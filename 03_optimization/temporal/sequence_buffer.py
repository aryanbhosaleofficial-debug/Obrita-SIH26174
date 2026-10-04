"""
Temporal sequence buffer.

Implementation status:
    Scaffold only.

Input:
    Per-frame features

Output:
    Sliding window of features ordered by frame_id

Owner:
    Module 03 — Optimization Sequence (Teammate 4: temporal section)
"""

from collections import deque

class SequenceBuffer:
    def __init__(self, maxlen=16): self._items=deque(maxlen=int(maxlen))
    def append(self,item): self._items.append(item)
    def clear(self): self._items.clear()
    def __len__(self): return len(self._items)
    def items(self): return list(self._items)
    @property
    def frame_gaps(self):
        ids=[x.get("frame_id") if isinstance(x,dict) else getattr(x,"frame_id",None) for x in self._items]
        return [b-a for a,b in zip(ids,ids[1:]) if isinstance(a,int) and isinstance(b,int) and b-a>1]
