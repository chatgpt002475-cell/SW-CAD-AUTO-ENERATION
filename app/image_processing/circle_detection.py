"""
Circle and Hole Detection
Identifies circular features, calculates circularity scores, and detects hole patterns.
"""

import math
from typing import Dict, Any, Optional
import cv2
import numpy as np


class CircleDetector:
    def __init__(self, circularity_thresh: float = 0.85):
        self.circularity_thresh = float(circularity_thresh)

    def analyze_contour_circularity(self, contour: np.ndarray) -> Dict[str, Any]:
        """
        Determines whether a contour represents a true circle / cylinder.
        Circularity = 4 * pi * Area / (Perimeter^2)
        """
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)

        result = {
            "is_circle": False,
            "circularity": 0.0,
            "center": None,
            "radius_px": 0.0,
            "diameter_px": 0.0
        }

        if perimeter <= 0:
            return result

        c_score = (4.0 * math.pi * area) / (perimeter * perimeter)
        result["circularity"] = round(c_score, 4)

        if c_score >= self.circularity_thresh:
            (cx, cy), radius = cv2.minEnclosingCircle(contour)
            result["is_circle"] = True
            result["center"] = (float(cx), float(cy))
            result["radius_px"] = float(radius)
            result["diameter_px"] = float(radius * 2.0)

        return result
