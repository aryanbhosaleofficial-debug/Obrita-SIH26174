"""Run the project pipeline over a demo image and print the detected chain code."""

from pathlib import Path

import cv2

from boundary_detection import detect_boundary
from chain_code import generate_chain_code
from preprocessing import preprocess_image


IMAGE_PATH = Path("images") / "sample_square.png"


def main() -> None:
    image = cv2.imread(str(IMAGE_PATH))
    if image is None:
        raise FileNotFoundError(f"Image not found: {IMAGE_PATH}")

    processed = preprocess_image(image, threshold_value=127)
    boundary_info = detect_boundary(processed["binary"])
    contour = boundary_info["selected_contour"]
    boundary_points = [tuple(map(int, point)) for point in contour.reshape(-1, 2)]
    start_index = min(
        range(len(boundary_points)),
        key=lambda index: (boundary_points[index][1], boundary_points[index][0]),
    )
    path = boundary_points[start_index:] + boundary_points[:start_index]
    start_point = path[0]
    chain_code = generate_chain_code(path)

    print(f"Loaded Image: {IMAGE_PATH}")
    print(f"Image Size: {image.shape[:2]}")
    print(f"Boundary Pixels: {len(path)}")
    print(f"Starting Point: {start_point}")
    print(f"Chain Code: {chain_code}")
    print(f"Formatted Chain Code: {''.join(str(value) for value in chain_code)}")


if __name__ == "__main__":
    main()
