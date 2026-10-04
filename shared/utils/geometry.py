"""
Geometry helpers shared across modules.

Implementation status:
    Scaffold only.

Conventions:
    - Image coordinates are pixels in the ORIGINAL source frame,
      origin top-left, x to the right, y downwards.
    - Boxes are (x1, y1, x2, y2) with x1 < x2 and y1 < y2.
    - Rack-relative coordinates are defined by RackReference
      (shared/schemas/spatial_feature_packet.py).
"""

# TODO: box_area, box_iou, clip_box_to_image
# TODO: point_to_box_distance
# TODO: angle_between(vector_a, vector_b) in degrees
