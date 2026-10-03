"""Chain-code generation and analysis for object boundaries."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

import numpy as np


DIRECTION_VECTORS = {
    0: (1, 0),
    1: (1, -1),
    2: (0, -1),
    3: (-1, -1),
    4: (-1, 0),
    5: (-1, 1),
    6: (0, 1),
    7: (1, 1),
}

DIRECTION_NAMES = {
    0: "Right",
    1: "Top-Right",
    2: "Up",
    3: "Top-Left",
    4: "Left",
    5: "Bottom-Left",
    6: "Down",
    7: "Bottom-Right",
}

NEIGHBOR_ORDER = [0, 1, 2, 3, 4, 5, 6, 7]


def get_direction(start: tuple[int, int], end: tuple[int, int]) -> int:
    """Return the 8-connected Freeman direction between two adjacent pixels."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]

    if dx == 1 and dy == 0:
        return 0
    if dx == 1 and dy == -1:
        return 1
    if dx == 0 and dy == -1:
        return 2
    if dx == -1 and dy == -1:
        return 3
    if dx == -1 and dy == 0:
        return 4
    if dx == -1 and dy == 1:
        return 5
    if dx == 0 and dy == 1:
        return 6
    if dx == 1 and dy == 1:
        return 7

    raise ValueError(f"Pixels are not neighbors in 8-connected space: {start} -> {end}")


def trace_boundary(binary_image: np.ndarray, start_point: tuple[int, int], max_iterations: int = 10000) -> list[tuple[int, int]]:
    """Trace the border of an object using a manual 8-neighbor search with loop protection."""
    if binary_image.ndim != 2:
        raise ValueError("The binary image must be 2D.")

    rows, cols = binary_image.shape
    x0, y0 = start_point
    if not (0 <= x0 < cols and 0 <= y0 < rows):
        raise ValueError(f"The starting point {start_point} is outside the image bounds.")

    object_mask = binary_image > 0
    boundary_mask = np.zeros_like(object_mask, dtype=bool)

    for y in range(1, rows - 1):
        for x in range(1, cols - 1):
            if object_mask[y, x]:
                neighbors = [
                    object_mask[y - 1, x - 1],
                    object_mask[y - 1, x],
                    object_mask[y - 1, x + 1],
                    object_mask[y, x - 1],
                    object_mask[y, x + 1],
                    object_mask[y + 1, x - 1],
                    object_mask[y + 1, x],
                    object_mask[y + 1, x + 1],
                ]
                if not all(neighbors):
                    boundary_mask[y, x] = True

    if not boundary_mask[y0, x0]:
        raise ValueError("The starting point is not on the object foreground.")

    path: list[tuple[int, int]] = [start_point]
    current = start_point
    previous = None
    visited: set[tuple[int, int]] = {start_point}
    iterations = 0

    while iterations < max_iterations:
        next_point = None
        for direction in NEIGHBOR_ORDER:
            dx, dy = DIRECTION_VECTORS[direction]
            nx = current[0] + dx
            ny = current[1] + dy

            if not (0 <= nx < cols and 0 <= ny < rows):
                continue
            if (nx, ny) == previous:
                continue
            if (nx, ny) in visited and (nx, ny) != start_point:
                continue
            if boundary_mask[ny, nx]:
                next_point = (nx, ny)
                break

        if next_point is None:
            break

        path.append(next_point)
        visited.add(next_point)
        previous = current
        current = next_point
        iterations += 1

        if current == start_point:
            break

    if len(path) < 3:
        raise ValueError("Boundary tracing failed. The object may be too small or too faint.")

    return path


def generate_chain_code(boundary_points: Iterable[tuple[int, int]]) -> list[int]:
    """Generate a Freeman 8-connected chain code from a traced boundary path."""
    points: list[tuple[int, int]] = []
    for point in boundary_points:
        normalized = (int(point[0]), int(point[1]))
        if not points or normalized != points[-1]:
            points.append(normalized)

    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(points) < 2:
        return []

    return [
        get_direction(points[index], points[(index + 1) % len(points)])
        for index in range(len(points))
    ]


def format_chain_code(codes: list[int], preview_length: int = 40) -> str:
    """Convert a chain-code list into a compact string."""
    visible = codes[:preview_length]
    return "".join(str(code) for code in visible)


def normalize_chain_code(codes: list[int]) -> list[int]:
    """Compute the first-difference chain code: d[i] = (code[i+1] - code[i]) mod 8."""
    if len(codes) < 2:
        return []

    normalized = []
    for index in range(len(codes) - 1):
        normalized.append((codes[index + 1] - codes[index]) % 8)
    return normalized


def direction_frequency(codes: list[int]) -> dict[int, int]:
    """Count how many times each direction appears in the chain code."""
    return dict(Counter(codes))


def compare_chain_codes(code_a: list[int], code_b: list[int]) -> float:
    """Return a simple similarity score based on sequence difference."""
    if not code_a and not code_b:
        return 100.0
    if not code_a or not code_b:
        return 0.0

    shorter = min(len(code_a), len(code_b))
    matches = 0
    for index in range(shorter):
        if code_a[index] == code_b[index]:
            matches += 1

    similarity = (matches / shorter) * 100.0
    return float(round(similarity, 2))
