"""Create simple sample images for testing the project."""

from pathlib import Path

import cv2
import numpy as np


OUTPUT_DIR = Path("images")
OUTPUT_DIR.mkdir(exist_ok=True)


def create_square_image(path: Path, size: int = 200) -> None:
    image = np.ones((size, size, 3), dtype=np.uint8) * 255
    cv2.rectangle(image, (40, 40), (size - 40, size - 40), (0, 0, 0), thickness=15)
    cv2.imwrite(str(path), image)


def create_triangle_image(path: Path, size: int = 220) -> None:
    image = np.ones((size, size, 3), dtype=np.uint8) * 255
    triangle_points = np.array([
        [size // 2, 25],
        [25, size - 25],
        [size - 25, size - 25],
    ], dtype=np.int32)
    cv2.drawContours(image, [triangle_points], 0, (0, 0, 0), thickness=15)
    cv2.imwrite(str(path), image)


def create_circle_image(path: Path, radius: int = 80, center: tuple[int, int] = (120, 120)) -> None:
    image = np.ones((240, 240, 3), dtype=np.uint8) * 255
    cv2.circle(image, center, radius, (0, 0, 0), thickness=12)
    cv2.imwrite(str(path), image)


if __name__ == "__main__":
    create_square_image(OUTPUT_DIR / "sample_square.png")
    create_triangle_image(OUTPUT_DIR / "sample_triangle.png")
    create_circle_image(OUTPUT_DIR / "sample_circle.png")
    print("Demo images generated in the images folder.")
