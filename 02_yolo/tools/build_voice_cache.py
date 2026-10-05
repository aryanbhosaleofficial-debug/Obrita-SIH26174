"""Build a verified WAV cache for one procedure on a machine where a backend works.

Typical use: run with --backend piper on an approved Linux machine, copy the
output folder to the Windows demo PC and pass its manifest.json via
--voice-cache. The Windows runtime then only plays these files. Never
downloads anything; the generator backend is recorded in the manifest.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from standalone import bootstrap

bootstrap()

from yolo.alerts.piper_tts import PiperTTS, VoiceUnavailable
from yolo.alerts.sapi5 import Sapi5TTS
from yolo.alerts.voice_cache import load_manifest, write_cache
from yolo.procedure.markdown_loader import load_procedure


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--procedure", type=Path, required=True)
    parser.add_argument("--backend", choices=("piper", "sapi5"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--piper-model", type=Path)
    parser.add_argument("--sapi-voice")
    args = parser.parse_args(argv)
    definition = load_procedure(args.procedure)
    if args.backend == "piper":
        backend = PiperTTS(args.piper_model)
        generator = {
            "backend": "piper",
            "voice": args.piper_model.name if args.piper_model else None,
            "voice_sha256": hashlib.sha256(args.piper_model.read_bytes()).hexdigest()
            if args.piper_model and args.piper_model.is_file()
            else None,
        }
    else:
        backend = Sapi5TTS(args.sapi_voice)
        generator = {"backend": "sapi5"}
    try:
        backend.load()
        if hasattr(backend, "probe"):
            backend.probe()
        if isinstance(backend, Sapi5TTS):
            generator["voice"] = backend.voice_description
        manifest = write_cache(definition, backend.synthesize, args.output, generator)
    except VoiceUnavailable as exc:
        print(json.dumps({"status": "FAILED", "reason": str(exc)}))
        return 2
    finally:
        backend.close()
    clips, report = load_manifest(manifest, definition)  # verify what we wrote
    print(
        json.dumps(
            {
                "status": "PASS" if not report["rejected"] else "INVALID",
                "manifest": str(manifest),
                "generator": generator,
                "entries": report["valid_entries"],
                "distinct_audio": len(clips),
                "rejected": report["rejected"],
            }
        )
    )
    return 0 if not report["rejected"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
