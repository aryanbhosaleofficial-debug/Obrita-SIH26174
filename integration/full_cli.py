"""One full-system CLI. Owner module runners remain standalone diagnostics."""
import argparse
from contextlib import ExitStack
from dataclasses import replace
import json
import logging
import ipaddress
from pathlib import Path
import sys
from uuid import uuid4

import yaml

ROOT = Path(__file__).resolve().parents[1]


def options(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-config", type=Path, default=ROOT / "configs/runtime.yaml")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--source", help="camera index or local video/image path (default camera 0)")
    source.add_argument("--synthetic", action="store_true", help="explicit inference fakes; no AI performance claim")
    parser.add_argument("--scenario", choices=("correct", "wrong-order", "skip", "repeated", "recovery", "fusion"), default="correct")
    parser.add_argument("--rotation", type=int, choices=(0, 90, 180), default=0, help="synthetic camera/setup rotation")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--gui", action="store_true")
    mode.add_argument("--no-gui", action="store_true", help="headless (default)")
    parser.add_argument("--gui-shot", type=Path, help="optional PNG screenshot on GUI EOF")
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--session-id")
    for name in ("procedure", "event-map", "pipeline-config", "camera-config", "boundary-config", "fusion-config", "tracking-config", "model", "classes", "pose-model", "hand-model"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--record", nargs="?", const="auto", help="record annotated video; optional .avi/.mp4 path")
    parser.add_argument("--record-fps", type=float)
    parser.add_argument("--log", type=Path, help="timestamped event JSONL; default unique session file")
    parser.add_argument("--diagnostics", type=Path, help="optional verbose per-frame JSONL")
    parser.add_argument("--voice", action="store_true", help="existing offline voice worker; optional failures degrade")
    parser.add_argument("--voice-backend", choices=("auto", "sapi5", "cached_wav", "piper"), default="auto")
    parser.add_argument("--voice-model", type=Path)
    parser.add_argument("--voice-cache", type=Path)
    parser.add_argument("--stream", action="store_true", help="optional local HTTP/MJPEG service")
    parser.add_argument("--stream-host")
    parser.add_argument("--stream-port", type=int)
    parser.add_argument("--realtime", action="store_true", help="pace synthetic input to 30 source frames/s")
    parser.add_argument("--action-interval", type=int, default=12, help="synthetic semantic action interval in frames; use 90 for a paced voice demo")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    path = args.runtime_config.resolve()
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    required = {"pipeline_config", "camera_config", "boundary_config", "fusion_config", "tracking_config", "procedure", "log_dir", "recording_dir", "synthetic_frames", "recording_fps", "stream_host", "stream_port"}
    if not isinstance(payload, dict) or set(payload) != {"runtime"} or not isinstance(payload["runtime"], dict) or set(payload["runtime"]) != required:
        raise ValueError("runtime YAML must contain exactly the documented runtime settings")
    cfg = payload["runtime"]
    for name in ("pipeline_config", "camera_config", "boundary_config", "fusion_config", "tracking_config", "procedure", "log_dir", "recording_dir"):
        if not isinstance(cfg[name], str) or not cfg[name].strip():
            raise ValueError(f"runtime.{name} must be a path")
        default = (path.parent / cfg[name]).resolve()
        setattr(args, name, getattr(args, name, None) or default)
    args.record_fps = args.record_fps if args.record_fps is not None else cfg["recording_fps"]
    if not isinstance(args.record_fps, (int, float)) or isinstance(args.record_fps, bool) or not 0 < args.record_fps <= 240:
        raise ValueError("record-fps must be finite in (0, 240]")
    count = cfg["synthetic_frames"]
    if type(count) is not int or count < 1:
        raise ValueError("runtime.synthetic_frames must be positive integer")
    if args.synthetic and args.max_frames is None:
        args.max_frames = count
    if args.max_frames is not None and args.max_frames <= 0:
        raise ValueError("max-frames must be positive")
    if args.action_interval < 1:
        raise ValueError("action-interval must be positive")
    if args.rotation and not args.synthetic:
        raise ValueError("--rotation is an explicit synthetic test; rotate/recalibrate the physical rack for live testing")
    if args.gui_shot and not args.gui:
        raise ValueError("--gui-shot requires --gui")
    args.stream_host = args.stream_host or cfg["stream_host"]
    args.stream_port = args.stream_port if args.stream_port is not None else cfg["stream_port"]
    if not isinstance(args.stream_host, str) or not args.stream_host or type(args.stream_port) is not int or not 0 <= args.stream_port <= 65535:
        raise ValueError("stream host/port invalid")
    if ipaddress.ip_address(args.stream_host).version != 4:
        raise ValueError("stream-host must be a literal IPv4 address; no DNS lookup")
    args.session_id = args.session_id or uuid4().hex
    if not args.session_id.strip() or len(args.session_id) > 128:
        raise ValueError("session-id must be nonempty and at most 128 characters")
    args.log = args.log or args.log_dir / f"session-{uuid4().hex}.jsonl"
    if args.record:
        args.record = args.recording_dir / f"session-{uuid4().hex}.avi" if args.record == "auto" else Path(args.record)
        if args.record.suffix.lower() not in (".avi", ".mp4"):
            raise ValueError("record output must be .avi or .mp4")
    return args


def build_runtime(args, *, gui=None, stop=None, controls=None):
    from boundary.boundary_pipeline import BoundaryPipeline
    from fusion.pipeline import FusionPipeline
    from integration.activity import ActivityAdapter
    from integration.chain import PerceptionChain
    from integration.full_synthetic import inputs, RotatedLandmarkBackend, SemanticScenario
    from integration.full_system import FullSystemRuntime
    from integration.milestone import MilestonePipeline
    from integration.outputs import SessionLog, AsyncRecorder, LocalStream, VoiceOutput
    from integration.sources import load_camera_config, packets
    from pose_tracking.config import load_config
    from pose_tracking.tracker import PoseHandTracker
    from procedure import load_procedure
    from shared.config import PipelineConfig
    from yolo.alerts.contracts import VoiceConfig

    resources = ExitStack()
    try:
        config = PipelineConfig.from_yaml(args.pipeline_config)
        tracking_config = load_config(args.tracking_config)
        camera_config = load_camera_config(args.camera_config)
        if args.model:
            config.detector.model_path = args.model.resolve()
        if args.classes:
            config.detector.classes_path = args.classes.resolve()
        if args.hand_model:
            config.hand_tracker.model_path = args.hand_model.resolve()
            tracking_config = replace(tracking_config, hand_model_path=args.hand_model.resolve())
        if args.pose_model:
            tracking_config = replace(tracking_config, pose_model_path=args.pose_model.resolve())
        mirrored = camera_config["source"].get("mirrored", False)
        config.hand_tracker.mirrored = mirrored
        tracking_config = replace(tracking_config, input_mirrored=mirrored).validate()
        definition = load_procedure(args.procedure)
        adapter = ActivityAdapter.from_yaml(args.event_map) if args.event_map else ActivityAdapter()
        boundary = BoundaryPipeline.from_yaml(args.boundary_config)
        fusion = FusionPipeline.from_yaml(args.fusion_config)
        config.validate()
        protected = [args.runtime_config, args.pipeline_config, args.camera_config, args.boundary_config,
            args.fusion_config, args.tracking_config, args.procedure, args.event_map,
            config.detector.model_path, config.detector.classes_path, config.detector.tracker_path,
            config.hand_tracker.model_path, tracking_config.pose_model_path, tracking_config.hand_model_path,
            args.voice_model, args.voice_cache]
        # Also protect owner configs referenced by pipeline.yaml.
        owner = yaml.safe_load(args.pipeline_config.read_text())
        if isinstance(owner, dict) and isinstance(owner.get("pipeline"), dict):
            protected += [args.pipeline_config.parent / v for v in owner["pipeline"].values() if isinstance(v, str)]
        source = args.source or "0"
        video = None if source.isdecimal() else Path(source)
        if not args.synthetic and video:
            if not video.is_file():
                raise FileNotFoundError(f"local video/image not found: {video}")
            protected.append(video)
        outputs = [p for p in (args.log, args.record, args.diagnostics, args.gui_shot) if p]
        if args.record:
            outputs.append(args.record.with_suffix(args.record.suffix + ".jsonl"))
        targets = [p.resolve() for p in outputs]
        if len(set(targets)) != len(targets) or any(p in {v.resolve() for v in protected if v} for p in targets):
            raise ValueError("output paths must be distinct and cannot overwrite inputs/configs/models")
        if args.synthetic:
            config, frames, detector, hands = inputs(config, args.max_frames, args.session_id, args.rotation,
                                                    box_demo=args.scenario != "fusion")
            frames = iter(frames)
            semantic = None if args.scenario == "fusion" else SemanticScenario(definition, args.scenario, args.action_interval)
            backend = RotatedLandmarkBackend(args.rotation)
        else:
            # Local assets are checked before camera acquisition or model initialization.
            missing = []
            for enabled, name, path in ((config.detector.backend == "ultralytics", "YOLO", config.detector.model_path),
                (config.hand_tracker.enabled and config.hand_tracker.backend == "mediapipe", "Module 03 hand", config.hand_tracker.model_path),
                (tracking_config.body_enabled, "Module 06 pose", tracking_config.pose_model_path),
                (tracking_config.hands_enabled, "Module 06 hand", tracking_config.hand_model_path)):
                if enabled and (path is None or not path.is_file()):
                    missing.append(f"{name} model not found: {path}")
            if missing:
                raise FileNotFoundError("; ".join(missing) + "; supply local model overrides or use --synthetic")
            frames = packets(camera_config, camera=int(source) if video is None else None,
                             video=video, session_id=args.session_id)
            detector = hands = backend = semantic = None
        if semantic is None:
            adapter.validate_vocabulary(definition, fusion.config)
        if args.gui_shot:
            args.gui_shot.parent.mkdir(parents=True, exist_ok=True)
        pipeline = MilestonePipeline(PerceptionChain(config, detector=detector, hand_tracker=hands), boundary, fusion)
        tracker = PoseHandTracker(tracking_config, backend)
        log = SessionLog(args.log, args.session_id)
        resources.callback(log.close)
        recorder = AsyncRecorder(args.record, args.record_fps) if args.record else None
        if recorder:
            resources.callback(recorder.close)
        stream = voice = None
        output_errors = {}
        if args.stream:
            try:
                stream = LocalStream(args.stream_host, args.stream_port)
                resources.callback(stream.close)
            except OSError as exc:
                output_errors["Streaming"] = str(exc)
                log.emit({"event": "output_error", "output": "Streaming", "reason": str(exc)})
        if args.voice:
            try:
                voice = VoiceOutput(definition, VoiceConfig(backend=args.voice_backend,
                    model_path=args.voice_model, cache_manifest=args.voice_cache), emit=log.emit)
                resources.callback(voice.close)
            except Exception as exc:
                output_errors["Voice"] = str(exc)
                log.emit({"event": "output_error", "output": "Voice", "reason": str(exc)})
        diagnostics = None
        if args.diagnostics:
            args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
            out = resources.enter_context(args.diagnostics.open("w", encoding="utf-8"))
            def diagnostics(row):
                out.write(json.dumps(row, allow_nan=False) + "\n")
        runtime = FullSystemRuntime(pipeline, tracker, definition, adapter=adapter, log=log,
            recorder=recorder, stream=stream, voice=voice, semantic_scenario=semantic,
            gui=gui, stop=stop, controls=controls, diagnostics=diagnostics,
            realtime_fps=30. if args.realtime or args.gui else None)
        runtime.health_errors.update(output_errors)
        for name in output_errors:
            runtime.health[name] = "DEGRADED"
        resources.callback(runtime.close)
        return runtime, frames, resources
    except BaseException:
        resources.close()
        raise


def main(argv=None):
    try:
        args = options(argv)
        logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                            format="%(levelname)s %(name)s: %(message)s")
        if args.gui:
            from integration.full_gui import run_gui
            summary = run_gui(build_runtime, args)
        else:
            runtime, frames, resources = build_runtime(args)
            with resources:
                summary = runtime.run(frames, max_frames=args.max_frames)
        print(json.dumps(summary, allow_nan=False))
        return 2 if summary.get("error") else 130 if summary.get("exit_reason") == "interrupt" else 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Full-system setup/runtime error [{type(exc).__name__}]: {exc}", file=sys.stderr)
        return 2
