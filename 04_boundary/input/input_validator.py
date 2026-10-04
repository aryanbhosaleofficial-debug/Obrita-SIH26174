"""Module 04 receiving contract; segmentation/target policy belongs downstream."""

from .contract_validator import BoundaryInputError, validate_boundary_input

__all__ = ["BoundaryInputError", "validate_boundary_input"]
