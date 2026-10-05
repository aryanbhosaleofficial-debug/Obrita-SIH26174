"""Only quality-gated confirmed boundary states are strong evidence."""
from shared.enums.boundary_state import BoundaryState


def extract(packet):
    return (packet.boundary_state.value, packet.confidence) if packet and packet.quality_ok and packet.state_confirmed and packet.boundary_state != BoundaryState.UNKNOWN else None
