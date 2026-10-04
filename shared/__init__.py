"""
Shared contracts and utilities for SIH26174.

This is the ONLY normally importable package shared by all modules
(e.g. `from shared.schemas.frame_packet import FramePacket`).

    schemas/  - packet dataclasses exchanged between modules
    enums/    - status / state enumerations used inside those packets
    utils/    - small, module-independent helpers

Rule:
    Modules must not redefine their own versions of these packets.
    A contract change is made here, reviewed by every affected module owner,
    and reflected in tests/test_packet_contracts.py.
"""
