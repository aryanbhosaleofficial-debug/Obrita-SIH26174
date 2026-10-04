"""The existing script/CLI delegates to the real prepared-frame stage."""

import json

import cv2
import numpy as np
import pytest
from yolo.pipeline import YoloPipeline

from yolo import cli


def test_cli_json_uses_actual_upstream_and_stage(
    tmp_path, monkeypatch, backend, detection, capsys
):
    image_path = tmp_path / "input.png"
    assert cv2.imwrite(str(image_path), np.zeros((400, 800, 3), np.uint8))
    core_path = tmp_path / "core.yaml"
    core_path.write_text(
        "perception: {preprocessing: {max_width: 400}}", encoding="utf-8"
    )
    fake = backend([[detection]])
    monkeypatch.setattr(cli, "YoloPipeline", lambda config: YoloPipeline(config, fake))
    assert (
        cli.main(
            [
                "--input",
                str(image_path),
                "--core-config",
                str(core_path),
                "--no-tracking",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok"
    assert output["image_width"] == 800 and output["image_height"] == 400
    assert output["detections"][0]["bbox"] == {"x1": 40, "y1": 60, "x2": 160, "y2": 180}
    assert output["timestamp_s"] == 0 and output["source_id"] == str(image_path)
    assert fake.initializations == 1 and fake.closed == 1


@pytest.mark.parametrize("present", [False, True])
def test_cli_rejects_missing_or_undecodable_image(tmp_path, present):
    path = tmp_path / "input.png"
    if present:
        path.write_bytes(b"not an image")
    assert cli.main(["--input", str(path)]) == 2


def test_cli_missing_local_weights_is_setup_error(tmp_path):
    image = tmp_path / "input.png"
    assert cv2.imwrite(str(image), np.zeros((40, 60, 3), np.uint8))
    assert (
        cli.main(
            [
                "--input",
                str(image),
                "--weights",
                str(tmp_path / "absent.pt"),
                "--no-tracking",
            ]
        )
        == 2
    )
