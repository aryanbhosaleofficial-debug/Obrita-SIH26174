"""Headless camera and Modules 01–05 commands over one authoritative pipeline."""
import argparse
from contextlib import ExitStack, closing
from dataclasses import asdict
import json
from pathlib import Path
import sys
from uuid import uuid4

from boundary.boundary_pipeline import BoundaryPipeline
from fusion.pipeline import FusionPipeline
from integration.chain import PerceptionChain
from integration.milestone import MilestonePipeline
from integration.sources import load_camera_config, packets
from integration.synthetic import configure, scene
from perception.core import FrameProcessor
from shared.config import PipelineConfig
from shared.errors import InitializationError
from yolo.inputs.opencv_source import InputSourceError

ROOT = Path(__file__).resolve().parents[1]


def parser(description):
    result = argparse.ArgumentParser(description=description)
    source = result.add_mutually_exclusive_group()
    source.add_argument("--synthetic", action="store_true", help="real stages with synthetic pixels and inference fakes")
    source.add_argument("--camera", type=int, help="camera index")
    source.add_argument("--video", type=Path, help="existing local video or image")
    result.add_argument("--camera-config", type=Path, default=ROOT / "configs/camera.yaml")
    result.add_argument("--max-frames", type=int, help="positive frame limit; synthetic default 36")
    result.add_argument("--session-id", default=None)
    result.add_argument("--output", type=Path, help="per-frame diagnostics JSONL; default stdout")
    return result


def validate_args(args, input_paths):
    if args.max_frames is not None and args.max_frames <= 0:
        raise ValueError("--max-frames must be positive")
    outputs = [p for p in (args.output, getattr(args, "events", None), getattr(args, "guidance", None)) if p is not None]
    protected = {p.resolve() for p in input_paths if p is not None}
    if any(p.resolve() in protected for p in outputs):
        raise ValueError("output paths must differ from input/config/model paths")
    if len(outputs) != len({p.resolve() for p in outputs}):
        raise ValueError("--output, --events and --guidance must differ")


def source_frames(args, camera_config):
    session = args.session_id or ("synthetic" if args.synthetic else uuid4().hex)
    if args.synthetic:
        frames, detector, hands = scene(args.max_frames or 36, session)
        return iter(frames), detector, hands, session
    # Config paths are documented relative to the repository root.
    config = camera_config
    if args.video is None and config["source"].get("video_path"):
        config["source"]["video_path"] = str(ROOT / config["source"]["video_path"])
    return packets(config, camera=args.camera, video=args.video, session_id=session), None, None, session


def destination(stack, path):
    if path is None:
        return sys.stdout
    path.parent.mkdir(parents=True, exist_ok=True)
    return stack.enter_context(path.open("w", encoding="utf-8"))


def write(stream, value):
    stream.write(json.dumps(value, allow_nan=False) + "\n")
    stream.flush()


def main(argv=None):
    args_parser = parser("Run the offline Modules 01–05 milestone.")
    args_parser.add_argument("--config", type=Path, default=ROOT / "configs/pipeline.yaml")
    args_parser.add_argument("--boundary-config", type=Path, default=ROOT / "configs/boundary.yaml")
    args_parser.add_argument("--fusion-config", type=Path, default=ROOT / "configs/fusion.yaml")
    args_parser.add_argument("--model", type=Path, help="local YOLO .pt/.onnx (overrides YAML)")
    args_parser.add_argument("--classes", type=Path, help="local YOLO class mapping (overrides YAML)")
    args_parser.add_argument("--hand-model", type=Path, help="local hand_landmarker.task (overrides YAML)")
    args_parser.add_argument("--pose-config", type=Path, help="optional Module 06 body-helper YAML")
    args_parser.add_argument("--pose-model", type=Path, help="enable optional body helper using this local .task")
    args_parser.add_argument("--target-object-track-id", type=int)
    args_parser.add_argument("--events", type=Path, help="confirmed events JSONL; default configured events_dir with a unique filename")
    args_parser.add_argument("--procedure", type=Path, help="optional procedure YAML consuming Module 05 ActivityEvent")
    args_parser.add_argument("--guidance", type=Path, help="displayable GuidanceDecision JSONL; requires --procedure")
    args = args_parser.parse_args(argv)
    count = events = errors = 0
    try:
        if args.guidance and not args.procedure:
            raise ValueError("--guidance requires --procedure")
        procedure = None
        if args.procedure:
            from procedure import ProcedureFSM, ProcedureIntegration, load_procedure
            procedure = ProcedureIntegration(ProcedureFSM(definition=load_procedure(args.procedure)))
        config = PipelineConfig.from_yaml(args.config)
        camera_config = load_camera_config(args.camera_config)
        if args.model:
            config.detector.model_path = args.model.resolve()
        if args.classes:
            config.detector.classes_path = args.classes.resolve()
        if args.hand_model:
            config.hand_tracker.model_path = args.hand_model.resolve()
        config.hand_tracker.mirrored = camera_config["source"].get("mirrored", False)
        config.validate()
        boundary = BoundaryPipeline.from_yaml(args.boundary_config)
        fusion = FusionPipeline.from_yaml(args.fusion_config)
        pose = None
        if args.synthetic and (args.pose_model or args.pose_config):
            raise ValueError("--synthetic substitutes inference; omit --pose-model/--pose-config")
        if args.pose_model or args.pose_config:
            from optimization.pose.pose_tracker import MediaPipePoseTracker
            from pose_tracking.config import load_config
            pose_config = load_config(args.pose_config or ROOT / "06_pose_tracking/config/pose_tracking.yaml")
            if args.pose_model:
                from dataclasses import replace
                pose_config = replace(pose_config, pose_model_path=args.pose_model.resolve())
            pose = MediaPipePoseTracker(pose_config)
        validate_args(args, [args.video, args.config, args.camera_config, args.boundary_config,
                             args.fusion_config, args.pose_config, args.pose_model, args.procedure,
                             config.detector.model_path, config.detector.classes_path,
                             config.hand_tracker.model_path])
        frames, detector, hands, session = source_frames(args, camera_config)
        if args.synthetic:
            config = configure(config)
        else:
            # Report every missing required asset before importing inference libraries.
            missing = []
            if config.detector.backend == "ultralytics" and (config.detector.model_path is None or not config.detector.model_path.is_file()):
                missing.append(f"YOLO model not found: {config.detector.model_path}; provide --model <local-model-path> or configure model_path")
            if config.hand_tracker.enabled and config.hand_tracker.backend == "mediapipe" and (config.hand_tracker.model_path is None or not config.hand_tracker.model_path.is_file()):
                missing.append(f"hand model not found: {config.hand_tracker.model_path}; provide --hand-model <local .task path> or configure model_path")
            if pose and not pose.config.pose_model_path.is_file():
                missing.append(f"pose model not found: {pose.config.pose_model_path}; provide --pose-model <local .task path>")
            if missing:
                raise InitializationError("\n".join(missing))
        chain = PerceptionChain(config, detector=detector, hand_tracker=hands, pose_tracker=pose)
        pipeline = MilestonePipeline(chain, boundary, fusion, target_object_track_id=args.target_object_track_id)
        with ExitStack() as stack:
            stack.callback(getattr(frames, "close", lambda: None))
            stack.enter_context(pipeline)
            output = destination(stack, args.output)
            event_path = args.events
            if event_path is None:
                directory = Path(fusion.config["output"]["events_dir"])
                if not directory.is_absolute():
                    directory = ROOT / directory
                event_path = directory / f"activities-{uuid4().hex}.jsonl"
            event_output = destination(stack, event_path)
            guidance_output = destination(stack, args.guidance) if args.guidance else None
            if procedure:
                initial = procedure.start()
                if guidance_output:
                    write(guidance_output, asdict(initial))
            for frame in frames:
                result = pipeline.process(frame)
                activity = result.activity
                decision = procedure.process(activity) if procedure else None
                if guidance_output and decision.should_display:
                    write(guidance_output, asdict(decision))
                count += 1
                if activity.status.value == "invalid_input":
                    errors += 1
                write(output, {
                    "mode": "synthetic" if args.synthetic else "local_inference",
                    "frame_id": frame.frame_id, "timestamp_s": frame.timestamp_s,
                    "source_id": frame.source_id, "session_id": frame.session_id,
                    "width": frame.width, "height": frame.height, "source_metadata": frame.metadata,
                    "statuses": {"01": result.upstream.prepared.status.value,
                                 "02": result.upstream.objects.status.value,
                                 "03": result.upstream.optimization.status.value,
                                 "04": result.boundary.status.value, "05": activity.status.value},
                    "detections": len(result.upstream.objects.detections),
                    "stable_detections": result.upstream.optimization.stable_detection_count,
                    "rack_reference_valid": result.upstream.optimization.spatial.reference_frame.valid,
                    "boundary_state": result.boundary.boundary_state.value,
                    "boundary_quality_ok": result.boundary.quality_ok,
                    "boundary_reasons": result.boundary.quality_reasons,
                    "activity": asdict(activity), "timings_ms": result.timings_ms,
                    **({"procedure": asdict(decision)} if decision else {}),
                })
                if activity.metadata["emitted"]:
                    write(event_output, asdict(activity))
                    events += 1
                if args.max_frames is not None and count >= args.max_frames:
                    break
        print(f"Processed {count} frames; confirmed events={events}; invalid frames={errors}; pose={'enabled' if pose else 'disabled (optional)'}", file=sys.stderr)
        return 2 if errors else 0
    except KeyboardInterrupt:
        print(f"Stopped cleanly after {count} frames; confirmed events={events}", file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, InitializationError, InputSourceError) as exc:
        print(f"Pipeline setup/runtime error: {exc}", file=sys.stderr)
        return 2


def camera_main(argv=None):
    args_parser = parser("Run Module 01 source acquisition and frame preparation.")
    args_parser.add_argument("--core-config", type=Path, default=ROOT / "configs/perception.yaml")
    args = args_parser.parse_args(argv)
    count = 0
    try:
        validate_args(args, [args.video, args.camera_config, args.core_config])
        core = FrameProcessor.from_yaml(args.core_config)
        frames, _, _, _ = source_frames(args, load_camera_config(args.camera_config))
        with ExitStack() as stack:
            stack.callback(getattr(frames, "close", lambda: None))
            output = destination(stack, args.output)
            for frame in frames:
                prepared = core.process(frame)
                write(output, {"frame_id": frame.frame_id, "timestamp_s": frame.timestamp_s,
                               "width": frame.width, "height": frame.height,
                               "source_id": frame.source_id, "session_id": frame.session_id,
                               "metadata": frame.metadata, "status": prepared.status.value,
                               "prepared_width": prepared.image.shape[1],
                               "prepared_height": prepared.image.shape[0],
                               "timings_ms": prepared.stage_timings_ms})
                count += 1
                if args.max_frames is not None and count >= args.max_frames:
                    break
        return 0
    except KeyboardInterrupt:
        print(f"Camera stopped cleanly after {count} frames", file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, InputSourceError) as exc:
        print(f"Camera setup/runtime error: {exc}", file=sys.stderr)
        return 2
