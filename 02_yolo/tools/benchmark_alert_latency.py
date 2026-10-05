"""Real voice-backend/device benchmark with injected actions, not camera perception.

Confirmation -> validator -> cache/synthesis -> PortAudio onset estimate.
No downloads. Cold samples include model load and procedure cache warm-up.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from standalone import bootstrap

bootstrap()

from yolo.alerts.contracts import AlertEvent, VoiceConfig
from yolo.alerts.timing import host_time
from yolo.procedure.assistant import ProcedureAssistant
from yolo.procedure.contracts import ConfirmedAction
from yolo.procedure.event_log import EventLog
from yolo.procedure.fast_actions import load_fast_config
from yolo.procedure.markdown_loader import load_procedure
from yolo.semantic.contracts import default_actions


class BenchmarkLog(EventLog):
    def __init__(self):
        super().__init__()
        self.all_records = []

    def emit(self, record):
        super().emit(record)
        self.all_records.append(dict(record))


def wait_ready(manager):
    with manager._condition:
        ready = manager._condition.wait_for(
            lambda: manager.status != "WARMING", timeout=180
        )
    if not ready or manager.status != "READY":
        raise RuntimeError(f"local Piper warm-up failed: {manager.status}")


def wait_played(app, frame_id):
    manager = app.alerts
    with manager._condition:
        done = manager._condition.wait_for(
            lambda: not manager._queue and manager._active is None, timeout=180
        )
    records = [
        r
        for r in app.log.all_records
        if r.get("event") == "audio_playback_started" and r.get("frame_id") == frame_id
    ]
    if not done or not records or manager.status not in {"READY", "PLAYING"}:
        failures = [
            r
            for r in app.log.all_records
            if r.get("event") in {"voice_error", "voice_unavailable"}
        ]
        raise RuntimeError(f"no successful real playback: {manager.status}; {failures}")
    return records[-1]


def violation(app, frame_id):
    """Correct first action, then wrong-object action while step two expected."""
    app.accept_confirmed(
        ConfirmedAction(
            "PICK_RED",
            "red_box",
            frame_id - 1,
            float(frame_id - 1),
            "injected_benchmark",
            host_time(),
        )
    )
    event = app.accept_confirmed(
        ConfirmedAction(
            "PICK_YELLOW",
            "yellow_box",
            frame_id,
            float(frame_id),
            "injected_benchmark",
            host_time(),
        )
    )
    if event.event != "WRONG_ORDER" or app.state.next_action != "MANIPULATE_RED":
        raise RuntimeError(
            "benchmark requires the supplied red/yellow sample procedure"
        )


def statistics(records):
    values = [r["warning_start_latency_ms"] for r in records]
    return {
        "sample_count": len(values),
        "minimum_ms": float(min(values)) if values else None,
        "median_ms": float(np.median(values)) if values else None,
        "p95_ms": float(np.percentile(values, 95)) if values else None,
        "maximum_ms": float(max(values)) if values else None,
        "target_1500_ms_device_estimate": bool(values) and max(values) <= 1500,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--piper-model", type=Path)
    parser.add_argument(
        "--voice-backend",
        choices=("auto", "cached_wav", "sapi5", "piper"),
        default="piper",
    )
    parser.add_argument("--voice-cache", type=Path, help="WAV cache manifest.json")
    parser.add_argument("--sapi-voice")
    parser.add_argument(
        "--procedure",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "examples/red_yellow_procedure.md",
    )
    parser.add_argument("--audio-device", type=int)
    parser.add_argument("--samples", type=int, default=10, help="warm cached samples")
    parser.add_argument("--cold-samples", type=int, default=3)
    parser.add_argument("--dynamic-samples", type=int, default=3)
    parser.add_argument(
        "--smoke-only", action="store_true", help="speak ORBITA voice ready once"
    )
    parser.add_argument("--smoke-text", default="ORBITA voice ready.")
    parser.add_argument("--jsonl", type=Path)
    args = parser.parse_args(argv)
    if (
        not 1 <= args.samples <= 50
        or not 0 <= args.cold_samples <= 10
        or not 0 <= args.dynamic_samples <= 10
    ):
        parser.error("warm samples 1..50; cold/dynamic samples 0..10")
    definition = load_procedure(args.procedure)
    fast = load_fast_config(
        Path(__file__).resolve().parents[1] / "examples/demo_fast_rules.yaml",
        default_actions(),
    )
    records = []
    results = {"cold": [], "warm_cached": [], "dynamic_uncached": []}

    def create():
        return ProcedureAssistant(
            definition,
            default_actions(),
            fast_config=fast,
            voice_config=VoiceConfig(
                model_path=args.piper_model,
                backend=args.voice_backend,
                cache_manifest=args.voice_cache,
                sapi_voice=args.sapi_voice,
                device=args.audio_device,
                speak_next_step=False,
                alert_cooldown_ms=0,
            ),
            event_log=BenchmarkLog(),
        )

    app = None
    try:
        if not args.smoke_only:
            for i in range(args.cold_samples):
                app = create()
                violation(app, 1000 + i * 2)
                results["cold"].append(wait_played(app, 1000 + i * 2))
                records.extend(app.log.all_records)
                app.close()
                app = None
        app = create()
        wait_ready(app.alerts)
        if args.smoke_only:
            app.alerts.enqueue(
                AlertEvent("SMOKE", args.smoke_text, 1, 1, 1, None, "NONE", host_time())
            )
            wait_played(app, 1)
        else:
            for kind, count in (
                ("warm_cached", args.samples),
                ("dynamic_uncached", args.dynamic_samples),
            ):
                for i in range(count):
                    app.reset()
                    if kind == "dynamic_uncached":
                        # Deliberately remove warmed PCM to exercise uncached synthesis.
                        app.alerts.cache.clear()
                    frame_id = (2000 if kind == "warm_cached" else 3000) + i * 2
                    violation(app, frame_id)
                    record = wait_played(app, frame_id)
                    if record["dynamic_synthesis"] != (kind == "dynamic_uncached"):
                        raise RuntimeError("unexpected cache path")
                    results[kind].append(record)
        records.extend(app.log.all_records)
        summary = {
            "status": "PASS",
            "injected_confirmed_violations": True,
            "production_validator_and_voice_backend": args.voice_backend,
            "voice_backends_used": sorted(
                {
                    str(r.get("voice_backend"))
                    for events in results.values()
                    for r in events
                }
            ),
            "clock": "host_perf_counter_seconds",
            "measurement_method": "portaudio_dac_estimate_first_non_silent_pcm",
            "acoustically_verified": False,
            "smoke_only": args.smoke_only,
            **{kind: statistics(events) for kind, events in results.items()},
        }
        print(json.dumps(summary), flush=True)
        if args.jsonl:
            args.jsonl.write_text(
                "\n".join(json.dumps(r) for r in [*records, summary]) + "\n",
                encoding="utf-8",
            )
        return 0
    except (RuntimeError, TimeoutError) as exc:
        if app is not None:
            records.extend(app.log.all_records)
        failures = [
            r for r in records if r.get("event") in {"voice_error", "voice_unavailable"}
        ]
        failure = {
            "status": "NOT VERIFIED",
            "reason": str(exc),
            "voice_failures": failures,
            **{kind: statistics(events) for kind, events in results.items()},
        }
        print(json.dumps(failure), flush=True)
        if args.jsonl:
            args.jsonl.write_text(
                "\n".join(json.dumps(r) for r in [*records, failure]) + "\n",
                encoding="utf-8",
            )
        return 2
    finally:
        if app is not None:
            app.close()


if __name__ == "__main__":
    raise SystemExit(main())
