"""
Gesture recognition.

Implementation status:
    Scaffold only.

Input:
    Gesture features over a temporal window

Output:
    GestureResult (label + confidence)

Owner:
    Module 03 — Optimization Sequence (Teammate 4: temporal section)
"""

from shared.schemas.optimization_packet import GestureResult

def recognize(history, min_history=2):
    if not history or len(history)<min_history: return GestureResult("unknown",0.0)
    values=[x.get("distance_norm") for x in history if x.get("distance_norm") is not None]
    if not values: return GestureResult("unknown",0.0)
    latest,first=values[-1],values[0]
    if latest<=.05: label,confidence="TOUCH",.85
    elif latest<first*.8: label,confidence="REACH",.8
    elif latest>first*1.2: label,confidence="RETRACT",.7
    else: label,confidence="unknown",.2
    return GestureResult(label,confidence,history[0].get("frame_id"),history[-1].get("frame_id"),True)
