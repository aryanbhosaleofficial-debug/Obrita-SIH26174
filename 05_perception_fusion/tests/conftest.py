"""Synthetic shared upstream packets; no inference assets or hardware."""
import pytest
from shared.enums.boundary_state import BoundaryState
from shared.schemas.boundary_packet import BoundaryOutputPacket
from shared.schemas.object_frame import ObjectFrame
from shared.schemas.optimization_packet import OptimizationOutputPacket
from shared.schemas.spatial_feature_packet import SpatialFeaturePacket
from shared.schemas.observations import BoundingBox, Detection, ReferenceFrameInfo


@pytest.fixture
def upstream():
    def make(fid=0, timestamp=None, track=7, contact=True, quality=True):
        ts = fid / 30 if timestamp is None else timestamp
        d = Detection(0, "sample_container", 0.9, BoundingBox(10, 10, 70, 70),
                      track, is_stable=True, continuity_key=track)
        objects = ObjectFrame(fid, ts, 320, 240, [d], source_id="unit", session_id="unit")
        spatial = SpatialFeaturePacket(fid, ts, reference_frame=ReferenceFrameInfo(valid=True, reference_id="rack"))
        opt = OptimizationOutputPacket(fid, ts, object_frame=objects, spatial=spatial,
                                       quality_ok=quality, source_id="unit", session_id="unit")
        boundary = BoundaryOutputPacket(
            fid, ts, target_object_track_id=track,
            boundary_state=BoundaryState.CONTACT if contact else BoundaryState.UNKNOWN,
            state_confirmed=contact, confirmed_frames=3 if contact else 0,
            hand_contact=contact, contact_confidence=0.8 if contact else 0.0,
            confidence=0.9, quality_ok=quality,
        )
        return opt, boundary
    return make
