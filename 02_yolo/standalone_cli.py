"""Offline Module 02 detector demo for webcam, local image or local video."""

import argparse
import json
import logging
from dataclasses import asdict, replace
from pathlib import Path

import cv2
import yaml
from yolo.adapters.standalone import adapt_image
from yolo.alerts.contracts import VoiceConfig
from yolo.core.config import load_config
from yolo.core.contracts import ConfigurationError, InitializationError
from yolo.core.pipeline import DetectorPipeline
from yolo.inputs.opencv_source import InputSourceError, OpenCVSource
from yolo.procedure.assistant import ProcedureAssistant
from yolo.procedure.event_log import EventLog
from yolo.procedure.fast_actions import load_fast_config
from yolo.procedure.markdown_loader import load_procedure
from yolo.semantic.contracts import SemanticConfig
from yolo.visualization.renderer import VisualizationError

MODULE_ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)


def load_semantic_config(path):
    if path is None:
        return SemanticConfig()
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or set(data) != {"semantic"}
        or not isinstance(data["semantic"], dict)
    ):
        raise ValueError("semantic YAML requires a single semantic mapping")
    try:
        return SemanticConfig(**data["semantic"])
    except TypeError as exc:
        raise ValueError(f"invalid semantic configuration: {exc}") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", required=True, help="camera index, local image or video"
    )
    parser.add_argument(
        "--config", type=Path, default=MODULE_ROOT / "config/standalone.yaml"
    )
    parser.add_argument("--semantic-config", type=Path)
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--classes", type=Path)
    parser.add_argument("--device")
    parser.add_argument(
        "--tracking", action=argparse.BooleanOptionalAction, default=None
    )
    parser.add_argument(
        "--vlm",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="local event-triggered semantics (enabled by default; --no-vlm disables)",
    )
    parser.add_argument("--ollama-host")
    parser.add_argument("--vlm-model")
    parser.add_argument("--procedure", type=Path, help="strict experiment Markdown")
    parser.add_argument(
        "--fast-config", type=Path, help="calibrated demo home/work ROI YAML"
    )
    parser.add_argument("--events-jsonl", type=Path, help="procedure/voice event log")
    parser.add_argument("--voice", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--voice-backend",
        choices=("auto", "cached_wav", "sapi5", "piper"),
        default="auto",
        help="auto falls back across local backends; an explicit choice never does",
    )
    parser.add_argument(
        "--voice-cache", type=Path, help="pre-generated WAV cache manifest.json"
    )
    parser.add_argument("--sapi-voice", help="installed SAPI5 voice name substring")
    parser.add_argument(
        "--piper-model", type=Path, help="local English .onnx with matching .onnx.json"
    )
    parser.add_argument("--audio-device", type=int)
    parser.add_argument("--alert-cooldown-ms", type=int, default=2500)
    parser.add_argument(
        "--speak-next-step", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--speak-success", action="store_true")
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument(
        "--output", type=Path, help="annotated image or MP4 (matching input kind)"
    )
    parser.add_argument("--jsonl", type=Path)
    parser.add_argument("--max-frames", type=int)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    pipeline = source = writer = json_file = assistant = event_log = None
    try:
        if args.max_frames is not None and args.max_frames < 1:
            raise ValueError("max-frames must be positive")
        config = load_config(args.config)
        config = replace(
            config,
            **{
                n: v
                for n, v in {
                    "model_path": args.weights,
                    "classes_path": args.classes,
                    "device": args.device,
                    "tracking": args.tracking,
                }.items()
                if v is not None
            },
        )
        semantic = load_semantic_config(args.semantic_config)
        semantic = replace(
            semantic,
            **{
                n: v
                for n, v in {
                    "enabled": args.vlm,
                    "host": args.ollama_host,
                    "model": args.vlm_model,
                }.items()
                if v is not None
            },
        )
        if args.procedure is None and (
            args.fast_config
            or args.events_jsonl
            or args.piper_model
            or args.voice_cache
            or args.sapi_voice
            or args.voice_backend != "auto"
        ):
            raise ValueError(
                "--fast-config, --events-jsonl and voice backend options "
                "require --procedure"
            )
        definition = (
            load_procedure(args.procedure, semantic.action_objects)
            if args.procedure
            else None
        )
        fast = (
            load_fast_config(args.fast_config, semantic.action_objects)
            if definition
            else None
        )
        voice = (
            VoiceConfig(
                enabled=args.voice,
                model_path=args.piper_model,
                device=args.audio_device,
                alert_cooldown_ms=args.alert_cooldown_ms,
                speak_next_step=args.speak_next_step,
                speak_success=args.speak_success,
                backend=args.voice_backend,
                cache_manifest=args.voice_cache,
                sapi_voice=args.sapi_voice,
            )
            if definition
            else None
        )
        source = OpenCVSource(args.source)
        if args.output:
            suffix = args.output.suffix.lower()
            if source.image is not None and suffix not in {
                ".png",
                ".jpg",
                ".jpeg",
                ".bmp",
                ".webp",
            }:
                raise ValueError("image output must use a supported image extension")
            if source.image is None and suffix != ".mp4":
                raise ValueError("video/camera output must end in .mp4")
        pipeline = DetectorPipeline(config, semantic_config=semantic)
        pipeline.initialize()
        if definition:
            event_log = EventLog(args.events_jsonl)
            assistant = ProcedureAssistant(
                definition,
                semantic.action_objects,
                fast_config=fast,
                voice_config=voice,
                event_log=event_log,
            )
        if args.jsonl:
            json_file = args.jsonl.open("w", encoding="utf-8")
        previous_shape = None
        failed = False
        for frame_id, timestamp, image in source:
            changed = previous_shape is not None and previous_shape != image.shape
            prepared = adapt_image(
                image,
                frame_id,
                timestamp,
                source_id=str(args.source),
                reset_required=changed,
            )
            previous_shape = image.shape
            objects = pipeline.process(prepared)
            failed |= objects.status in ("error", "invalid_input")
            if assistant:
                assistant.observe(
                    objects,
                    pipeline.semantic_result,
                    reset_required=prepared.reset_required,
                )
            display = pipeline.render(prepared, objects)
            if assistant:
                from yolo.visualization.procedure_overlay import render_procedure

                display = render_procedure(
                    display,
                    assistant.state,
                    voice_status=assistant.alerts.status,
                    warning_latency_ms=assistant.alerts.last_latency_ms,
                    voice_backends=assistant.alerts.backend_status,
                )
            result = {
                "objects": asdict(objects),
                "semantic": asdict(pipeline.semantic_result)
                if pipeline.semantic_result
                else None,
                "vlm_status": pipeline.semantic.status.value,
            }
            if assistant:
                result["procedure"] = asdict(assistant.state)
                result["voice_status"] = assistant.alerts.status
                result["voice_backends"] = assistant.alerts.backend_status
            line = json.dumps(result)
            print(line, flush=True)
            if json_file:
                json_file.write(line + "\n")
                json_file.flush()
            if args.output:
                if source.image is not None:
                    if not cv2.imwrite(str(args.output), display):
                        raise VisualizationError("cannot write annotated image")
                else:
                    h, w = display.shape[:2]
                    if writer is None:
                        writer = cv2.VideoWriter(
                            str(args.output),
                            cv2.VideoWriter.fourcc(*"mp4v"),
                            source.fps,
                            (w, h),
                        )
                        if not writer.isOpened():
                            raise VisualizationError(
                                "cannot open annotated video output"
                            )
                        output_shape = display.shape
                    if display.shape != output_shape:
                        raise VisualizationError(
                            "video frame size changed; output writer cannot resize"
                        )
                    writer.write(display)
            if not args.no_display:
                cv2.imshow("ORBITA Module 02", display)
                key = cv2.waitKey(0 if source.image is not None else 1) & 0xFF
                if key in (27, ord("q")):
                    break
            if args.max_frames and frame_id + 1 >= args.max_frames:
                break
        return 1 if failed else 0
    except (
        ConfigurationError,
        InitializationError,
        InputSourceError,
        VisualizationError,
        OSError,
        ValueError,
        yaml.YAMLError,
        cv2.error,
    ) as exc:
        LOGGER.error("Module 02 failed [%s]: %s", type(exc).__name__, exc)
        return 2
    finally:
        if assistant is not None:
            assistant.close()
        elif event_log is not None:
            event_log.close()
        if writer is not None:
            writer.release()
        if json_file is not None:
            json_file.close()
        if pipeline is not None:
            pipeline.close()
        if source is not None:
            source.close()
        if not args.no_display:
            cv2.destroyAllWindows()
