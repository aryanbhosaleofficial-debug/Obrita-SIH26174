"""Shared headless frame source adapter; hardware is outside Module 01 processing."""
from pathlib import Path
import math

import cv2
import yaml

from shared.config import ConfigurationError
from shared.schemas.frame_packet import FramePacket
from yolo.inputs.opencv_source import OpenCVSource


def load_camera_config(path):
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid camera YAML: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("source"), dict) or not isinstance(data.get("capture"), dict):
        raise ConfigurationError("camera config requires source and capture mappings")
    return data


def packets(camera_config, *, camera=None, video=None, session_id="default"):
    source_cfg = camera_config["source"]
    capture_cfg = camera_config["capture"]
    if camera is None and video is None:
        if source_cfg.get("type") == "camera":
            camera = source_cfg.get("camera_index")
        elif source_cfg.get("type") == "video":
            video = source_cfg.get("video_path")
        else:
            raise ConfigurationError("source.type must be camera or video")
    if camera is None and not video:
        raise ConfigurationError("camera source is unset; provide --camera 0 or --video <local file>")
    if camera is not None and (type(camera) is not int or camera < 0):
        raise ConfigurationError("camera index must be a nonnegative integer")
    if type(source_cfg.get("mirrored", False)) is not bool:
        raise ConfigurationError("source.mirrored must be boolean")
    # Resolve configured video paths against the repository; CLI paths use cwd.
    if video is not None and camera is None:
        video = Path(video)
        if not video.is_file():
            raise ConfigurationError(f"local video/image not found: {video}")
    with OpenCVSource(camera if camera is not None else str(video)) as reader:
        if camera is not None and reader.capture is not None:
            for key, prop in (("requested_width", cv2.CAP_PROP_FRAME_WIDTH), ("requested_height", cv2.CAP_PROP_FRAME_HEIGHT), ("requested_fps", cv2.CAP_PROP_FPS)):
                value = capture_cfg.get(key)
                if value is not None:
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                        raise ConfigurationError(f"{key} must be positive or null")
                    reader.capture.set(prop, value)
            actual_fps = reader.capture.get(cv2.CAP_PROP_FPS)
        else:
            actual_fps = reader.fps
        for fid, timestamp, image in reader:
            if source_cfg.get("mirrored", False):
                image = cv2.flip(image, 1)
            height, width = image.shape[:2]
            yield FramePacket(fid, timestamp, image, width, height,
                              source_id=f"camera_{camera}" if camera is not None else str(video),
                              session_id=session_id,
                              metadata={"actual_width": width, "actual_height": height,
                                        "reported_fps": actual_fps, "mirrored": source_cfg.get("mirrored", False)})
