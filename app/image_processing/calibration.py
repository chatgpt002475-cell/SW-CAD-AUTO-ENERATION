"""
Scale Calibration and Coordinate Reference
Converts pixel measurements to real physical engineering units (mm or inches).
Never silently assumes pixels equal millimeters.
"""

import math
from typing import Tuple, Optional


class ScaleCalibrator:
    def __init__(self, units: str = "mm"):
        self.units = units.lower()
        if self.units not in ("mm", "inch", "in"):
            raise ValueError("Supported units are 'mm' or 'inch'.")
        self.mm_per_pixel = None
        self.is_calibrated = False

    def calibrate_by_known_dimension(self, pixel_span: float, real_dimension: float, dimension_unit: str = "mm") -> float:
        """
        Calibrates scale from a known pixel span and corresponding real-world measurement.
        """
        if pixel_span <= 0:
            raise ValueError("Pixel span must be greater than zero.")
        if real_dimension <= 0:
            raise ValueError("Real dimension must be greater than zero.")

        # Convert to millimeters internally
        if dimension_unit.lower() in ("inch", "in"):
            real_mm = real_dimension * 25.4
        else:
            real_mm = real_dimension

        self.mm_per_pixel = real_mm / pixel_span
        self.is_calibrated = True
        return self.mm_per_pixel

    def calibrate_by_points(self, pt1: Tuple[float, float], pt2: Tuple[float, float], real_dimension: float, dimension_unit: str = "mm") -> float:
        """Calibrates scale from two user-selected landmark points."""
        dx = pt2[0] - pt1[0]
        dy = pt2[1] - pt1[1]
        dist_px = math.hypot(dx, dy)
        return self.calibrate_by_known_dimension(dist_px, real_dimension, dimension_unit)

    def px_to_mm(self, pixels: float) -> float:
        if not self.is_calibrated or self.mm_per_pixel is None:
            raise RuntimeError("Scale calibration required: mm_per_pixel is undefined.")
        return pixels * self.mm_per_pixel

    def get_scale_factor(self) -> float:
        if not self.is_calibrated:
            raise RuntimeError("Calibrator has not been calibrated.")
        return self.mm_per_pixel
