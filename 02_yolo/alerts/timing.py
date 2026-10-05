"""Shared high-resolution monotonic host basis for confirmation/audio latency."""

from time import perf_counter


def host_time():
    return perf_counter()
