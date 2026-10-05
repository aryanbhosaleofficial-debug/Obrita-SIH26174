# Module 04 targeted repair — independent re-review checklist

- [x] Bright-on-dark and dark-on-light select the object, not the ROI border.
- [x] Uniform grey/black/white ROI produces no valid high-confidence geometry.
- [x] Seeded intensity and bimodal noise rejected conservatively.
- [x] Foreground occupancy, ROI border/fill, contrast and fragmentation are explicit checks.
- [x] Legitimate single-edge clipping is not automatically rejected.
- [x] Tight YOLO boxes have consistent 0.1 Python/YAML padding and clipped-ROI integration tests.
- [x] Tolerated dropped IDs preserve confirmation; motion is normalized by source-frame interval.
- [x] Excess gaps/time gaps reset; duplicate/backwards inputs remain rejected.
- [x] Segmentation quality bounds confidence; rejected quality publishes zero confidence.
- [x] Rejected quality cannot publish contact or confirmed state.
- [x] Real Module 03 -> Module 04 path exercises reviewed segmentation scenarios.
- [x] Supported STATIONARY/MOVING/CONTACT/SEPARATING states have multi-frame evidence.
- [x] N-of-M confirmation, counts, warm-up, resets and bounded buffers tested.
- [x] Source/session changes require explicit reset; malformed inputs are explicit.
- [x] Standalone caller can supply rack validity without invented calibration.
- [x] Unknown keys/unsupported enabled settings fail; YAML comments match behavior.
- [x] Implemented areas have real tests; only five named future features remain skipped.
- [x] Shared schemas and Modules 01-03/05/06/GUI/FSM remain unchanged.
- [x] Compile, contract, upstream, full suite and offline smoke checks executed.
- [ ] Independent reviewer approves freezing (not decided by implementer).
- [ ] Rack-relative orientation / ROTATING.
- [ ] Optimization cross-check, hand-expanded ROI and HSV.
- [ ] Contour association/resampling and illumination correction.
- [ ] Module 05 consumer (unimplemented outside this repair).
- [ ] Centralized future boundary source/session schema extension.
- [ ] Tune demonstration footage / benchmark performance and accuracy.

Prototype evidence only. No flight certification or microgravity validation.
See FINAL_P1_REPORT.md for the latest commands/counts and cleanup status;
REPAIR_REPORT.md preserves the earlier major-repair record.
