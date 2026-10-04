# Module 01 integration decision

## Architectural conflict

The scaffold assigns camera acquisition/orchestration to `01_perception_core`,
YOLO to `02_yolo`, and pose/hands/interaction to `03_optimization`. The requested
Module 01 implementation covers the full perception layer but explicitly
excludes owning the camera or main application orchestration. These are two
different decomposition plans. Implementing both as a single hidden chain would
duplicate inference and misrepresent ownership.

The new import-safe `perception` package implements the requested Module 01.
The numbered scaffold remains intact as the team's historical planning layout;
no functional teammate code was replaced. Other modules should integrate using
the contracts below, then the team can resolve their eventual ownership plan.
There is no implicit loading of numbered packages and no normal invalid Python
`from 02_yolo ...` import.

## Input and output

```text
External frame source
    -> existing shared.schemas.FramePacket
    -> perception.PerceptionPipeline.process(packet)
    -> shared.schemas.PerceptionFrameResult
    -> external Module 02 / temporal HAR consumer
```

The existing source packet keeps `frame_id`, monotonic `timestamp_s`, image,
actual width/height, source/color format and source status. It is not redefined.
The new result contract also lives in `shared/schemas` and is re-exported from
`perception.contracts`. Pixel geometry always refers to the original image.
The source image and injected inference observations are never modified.

## Module 02 boundary

In the requested decomposition, the next reasoning consumer accepts
`PerceptionFrameResult` directly. It may use:

* `detections[*].is_stable`, `duration_frames`, real `track_id` or `None`;
* `hands[*].identity_persistent` rather than handedness to assess identity;
* `associations` for raw geometric evidence and ambiguity;
* confirmed `interactions` and their current frame's detection/hand indices;
* confidence components, coordinate validity, status and warnings;
* preserved source identity/time and measured stage timings.

Per-frame list indices are **not persistent IDs**. `object_id` is the string form
of a supplied backend track ID or `None`. The same numerical track ID can be
reused by a backend in a later session, so namespace it by source/session.
`identity_reliable` is a continuity flag, not a guarantee that a tracker never
swaps identities. Missing observations are absent, not emitted with stale data.

For existing scaffold code expecting Module 02's `ObjectFrame`, use:

```python
from perception.integration import to_object_frame

result = pipeline.process(frame_packet)
object_frame = to_object_frame(result)
# Pass object_frame to existing object-only consumers.
# Pass result itself to hand/interaction/temporal consumers.
```

The bridge copies existing `DetectedObject` fields, stability and real IDs, with
unchanged frame/time/dimensions/status. It leaves `reference_anchors` empty:
manual calibration is not evidence of a detected rack anchor. It does not map
hand geometry into invented gesture/optimization/HAR packets. If Module 02 will
continue owning YOLO inference, inject its detector through `ObjectDetector`
instead of running YOLO twice. The adapter must return local normalized
`Detection` dataclasses in its input image's pixels.

## Required consumer rules

Interpretation belongs downstream. Near/contact candidates must not be treated
as verified physical touch, grasping, step completion or procedure order. Read
`coordinate_frame_valid` before using rack polygons/landmarks. Fallback image
fractions are explicitly labelled and not orientation invariant. Inspect
`is_stable`, identity and confidence; preserve warning/status uncertainty.

One pipeline handles one ordered source per session. The frame source supplies
strictly increasing frame IDs and monotonic timestamps. Call `reset()` before
switching source/replaying a session, and `close()` on shutdown. Use a dedicated
worker; the pipeline does not drive GUI events or create application threads.
Downstream HAR, alerts, logging and procedure state remain external.
