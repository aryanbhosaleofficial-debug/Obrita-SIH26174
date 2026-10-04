"""
Logging setup shared by all modules.

Implementation status:
    Scaffold only.

Rules:
    - Logs go to the local logs/ directory (relative to the repository root).
    - No remote / cloud log sinks (offline requirement).
"""

# TODO: get_logger(name: str) -> logging.Logger with a consistent format
# TODO: optional file handler writing to logs/<session>.log
