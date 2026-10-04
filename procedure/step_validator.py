"""
Step validation.

Implementation status:
    Scaffold only.

Input:
    ActivityEvent + current procedure state

Output:
    StepOutcome (correct / wrong order / skipped / unrelated)

Owner:
    Procedure FSM (downstream consumer of Module 05)
"""

# TODO: Compare event activity and target object with expected step.
# TODO: Detect skipped steps (event matches a later step).
