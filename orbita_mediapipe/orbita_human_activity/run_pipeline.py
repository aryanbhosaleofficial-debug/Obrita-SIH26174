"""CLI Entry point for running ORBITA on live camera, video file, or smoke test."""

import argparse
import os
import sys

from orbita_human_activity.pipeline.orbita_pipeline import OrbitaHARPipeline
from orbita_human_activity.pipeline.pose_adapter import MediaPipePoseLandmarkerRunner
from orbita_human_activity.pipeline.serialization import DataLogger


def main():
    parser = argparse.ArgumentParser(description="ORBITA On-Board BAS Human Activity Recognition Runner")
    parser.add_argument("--camera", type=int, default=None, help="Camera device index (e.g. 0 for built-in webcam)")
    parser.add_argument("--video", type=str, default=None, help="Path to video file (.mp4, .avi, etc.)")
    parser.add_argument("--model-path", type=str, default="models/pose_landmarker.task", help="Path to MediaPipe pose_landmarker.task")
    parser.add_argument("--max-frames", type=int, default=None, help="Maximum number of frames to process")
    parser.add_argument("--display", action="store_true", help="Display visual video output window")
    parser.add_argument("--smoke-test", action="store_true", help="Run synthetic offline smoke test pipeline")
    parser.add_argument("--output-dir", type=str, default="output_logs", help="Directory for JSONL and CSV logs")
    parser.add_argument("--no-fallback", action="store_true", help="Strict mode: abort if real model asset is absent")

    args = parser.parse_args()

    # Pre-flight asset check
    resolved_model_path = MediaPipePoseLandmarkerRunner.resolve_model_asset_path(args.model_path)
    has_model_asset = os.path.exists(resolved_model_path)
    if not has_model_asset and args.no_fallback:
        print(f"[ERROR] Required model asset '{args.model_path}' not found.")
        print("[ERROR] Please download Google MediaPipe Pose Landmarker task bundle:")
        print("        https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task")
        sys.exit(1)

    logger = DataLogger(output_dir=args.output_dir, session_id="CLI_RUN")
    pose_runner = MediaPipePoseLandmarkerRunner(
        model_asset_path=resolved_model_path,
        num_poses=2,
        use_synthetic_fallback=(not args.no_fallback)
    )
    pipeline = OrbitaHARPipeline(pose_runner=pose_runner, logger=logger)

    if args.smoke_test:
        print("[ORBITA] Executing synthetic smoke test pipeline...")
        res = pipeline.run_smoke_pipeline(num_frames=args.max_frames or 60)
        print(f"[ORBITA] Smoke test completed: {res['status']}, frames: {res['frames_processed']}, predictions: {res['predictions_count']}")
        return

    source = args.camera if args.camera is not None else args.video
    if source is None:
        print("[ORBITA] No input source specified. Use --camera <index>, --video <path>, or --smoke-test.")
        return

    print(f"[ORBITA] Starting pipeline on source: {source} (Real detector: {pose_runner.is_real_detector})")
    res = pipeline.run_video(source=source, max_frames=args.max_frames, display=args.display)
    print(f"[ORBITA] Video run finished: {res}")


if __name__ == "__main__":
    main()
