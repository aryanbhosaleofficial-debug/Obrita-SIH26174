"""Modules 01–06 headless composition, reusing the existing milestone pipeline."""
from contextlib import ExitStack
from dataclasses import asdict, replace
import logging
from pathlib import Path

from pose_tracking.config import DEFAULT_CONFIG_PATH, load_config
from pose_tracking.integration import TrackingIntegration
from pose_tracking.synthetic import SyntheticLandmarkBackend
from pose_tracking.tracker import PoseHandTracker


def main(argv=None) -> int:
    from boundary.boundary_pipeline import BoundaryPipeline
    from fusion.pipeline import FusionPipeline
    from integration.chain import PerceptionChain
    from integration.cli import ROOT, destination, parser, source_frames, validate_args, write
    from integration.milestone import MilestonePipeline
    from integration.sources import load_camera_config
    from integration.synthetic import configure
    from shared.config import PipelineConfig
    from shared.enums.module_status import ModuleStatus

    args_parser = parser("Run Modules 01–06 offline, with explicit inference-only synthetic mode.")
    args_parser.add_argument("--config", type=Path, default=ROOT / "configs/pipeline.yaml")
    args_parser.add_argument("--tracking-config", type=Path, default=DEFAULT_CONFIG_PATH)
    args_parser.add_argument("--boundary-config", type=Path, default=ROOT / "configs/boundary.yaml")
    args_parser.add_argument("--fusion-config", type=Path, default=ROOT / "configs/fusion.yaml")
    args_parser.add_argument("--model", type=Path, help="local YOLO weights")
    args_parser.add_argument("--pose-model", type=Path, help="local pose .task")
    args_parser.add_argument("--hand-model", type=Path, help="local hand .task, shared with Module 03")
    args = args_parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        config = PipelineConfig.from_yaml(args.config)
        tracking_config = load_config(args.tracking_config)
        if args.model:
            config.detector.model_path = args.model.resolve()
        if args.pose_model:
            tracking_config = replace(tracking_config, pose_model_path=args.pose_model.resolve())
        if args.hand_model:
            config.hand_tracker.model_path = args.hand_model.resolve()
            tracking_config = replace(tracking_config, hand_model_path=args.hand_model.resolve())
        camera_config = load_camera_config(args.camera_config)
        mirrored = camera_config["source"].get("mirrored", False)
        config.hand_tracker.mirrored = mirrored
        tracking_config = replace(tracking_config, input_mirrored=mirrored).validate()
        validate_args(args, [args.video, args.config, args.camera_config, args.tracking_config,
                             args.boundary_config, args.fusion_config, config.detector.model_path,
                             config.detector.classes_path, config.hand_tracker.model_path,
                             tracking_config.pose_model_path, tracking_config.hand_model_path])
        frames, detector, hands, session = source_frames(args, camera_config)
        if args.synthetic:
            config = configure(config)
        pipeline = MilestonePipeline(
            PerceptionChain(config, detector=detector, hand_tracker=hands),
            BoundaryPipeline.from_yaml(args.boundary_config),
            FusionPipeline.from_yaml(args.fusion_config),
        )
        tracker = PoseHandTracker(tracking_config,
                                  SyntheticLandmarkBackend() if args.synthetic else None)
        errors = count = 0
        with ExitStack() as stack:
            stack.callback(getattr(frames, "close", lambda: None))
            stack.enter_context(tracker)
            stack.enter_context(pipeline)
            stream = destination(stack, args.output)
            adapter = TrackingIntegration(tracker)
            for packet in frames:
                milestone = pipeline.process(packet)
                tracked = adapter.process(milestone)
                count += 1
                errors += any(part.status in (ModuleStatus.ERROR, ModuleStatus.INVALID_INPUT)
                              for part in (milestone.upstream.prepared, milestone.upstream.objects,
                                           milestone.upstream.optimization, milestone.boundary,
                                           milestone.activity, tracked))
                write(stream, {"synthetic": args.synthetic, "activity": asdict(milestone.activity),
                               "tracking": asdict(tracked)})
                if args.max_frames and count >= args.max_frames:
                    break
        logging.info("Modules 01-06: %d frames, %d pipeline errors; synthetic=%s", count, errors, args.synthetic)
        return 1 if errors else 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        logging.error("Modules 01–06 stopped [%s]: %s", type(exc).__name__, exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
