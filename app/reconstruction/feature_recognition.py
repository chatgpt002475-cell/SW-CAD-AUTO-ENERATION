"""
Feature Recognition Engine
Identifies mechanical design primitives from calibrated contours and geometry.
"""

from typing import List, Dict, Any, Tuple
import math
import cv2
import numpy as np

from app.image_processing.circle_detection import CircleDetector
from app.image_processing.contour_detection import ContourDetector
from .uncertainty import UncertaintyReporter


class FeatureRecognizer:
    def __init__(self, circle_detector: CircleDetector = None, contour_detector: ContourDetector = None):
        self.cd = circle_detector or CircleDetector()
        self.contour_detector = contour_detector or ContourDetector()
        self.uncertainty = UncertaintyReporter()

    def recognize_features_from_part(
        self,
        part_data: Dict[str, Any],
        scale_mm_per_px: float,
        img_center: Tuple[float, float],
        base_thickness_mm: float = 12.0
    ) -> Dict[str, Any]:
        """
        Analyzes outer contour and internal holes of a part and produces recognized mechanical features.
        """
        outer_cnt = part_data["outer_contour"]
        holes = part_data.get("holes", [])
        cx_img, cy_img = img_center

        # 1. Base Plate Profile
        outer_pts_px = self.contour_detector.approximate_polygon(outer_cnt)
        outer_pts_mm = [
            (
                round((px - cx_img) * scale_mm_per_px, 2),
                round(-(py - cy_img) * scale_mm_per_px, 2)
            )
            for px, py in outer_pts_px
        ]

        # Check if base is cylindrical or prismatic
        base_circ = self.cd.analyze_contour_circularity(outer_cnt)
        is_cylindrical = base_circ["is_circle"]

        features = {
            "base_feature": {
                "type": "CylindricalBase" if is_cylindrical else "PrismaticBase",
                "points_mm": outer_pts_mm,
                "thickness_mm": base_thickness_mm,
                "diameter_mm": round(base_circ["diameter_px"] * scale_mm_per_px, 2) if is_cylindrical else None,
                "confidence": 0.95
            },
            "holes": [],
            "pockets": [],
            "flanges": []
        }

        self.uncertainty.log_assumption(
            "BasePlate", "thickness_mm", base_thickness_mm,
            "Thickness inferred from user specification / default because input is a single 2D projection.",
            confidence=0.85
        )

        # 2. Analyze inner voids (holes vs pockets vs slots)
        for idx, h_cnt in enumerate(holes):
            h_circ = self.cd.analyze_contour_circularity(h_cnt)
            if h_circ["is_circle"]:
                # Circular hole
                px_cx, px_cy = h_circ["center"]
                x_mm = round((px_cx - cx_img) * scale_mm_per_px, 2)
                y_mm = round(-(px_cy - cy_img) * scale_mm_per_px, 2)
                dia_mm = round(h_circ["diameter_px"] * scale_mm_per_px, 2)

                features["holes"].append({
                    "id": f"Hole_{idx+1}",
                    "type": "ThroughHole",
                    "center_x_mm": x_mm,
                    "center_y_mm": y_mm,
                    "diameter_mm": dia_mm,
                    "depth_mm": base_thickness_mm,
                    "through_all": True,
                    "confidence": h_circ["circularity"]
                })
            else:
                # Slot or rectangular pocket
                h_pts_px = self.contour_detector.approximate_polygon(h_cnt)
                h_pts_mm = [
                    (
                        round((px - cx_img) * scale_mm_per_px, 2),
                        round(-(py - cy_img) * scale_mm_per_px, 2)
                    )
                    for px, py in h_pts_px
                ]
                features["pockets"].append({
                    "id": f"Pocket_{idx+1}",
                    "type": "ThroughSlotOrPocket",
                    "points_mm": h_pts_mm,
                    "depth_mm": base_thickness_mm,
                    "through_all": True,
                    "confidence": 0.88
                })

        return features
