"""
Module status reported by every module in every output packet.

Originating module: all modules (01-05)
Consuming component: next module in the pipeline, application health monitor
"""

from enum import Enum


class ModuleStatus(str, Enum):
    """Processing status of a module for one frame."""

    OK = "ok"  # output is complete and passed the module's own checks
    DEGRADED = "degraded"  # output exists but some parts are missing / low quality
    NO_DETECTION = "no_detection"  # module ran correctly but found nothing to report
    INVALID_INPUT = "invalid_input"  # upstream packet failed validation
    ERROR = "error"  # module failed while processing this frame
    FAILED = ERROR  # spelling alias; existing wire value preserved
