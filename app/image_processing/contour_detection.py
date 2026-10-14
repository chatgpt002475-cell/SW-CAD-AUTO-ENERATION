"""
Contour Detection and Hierarchy Analysis
Extracts outer solid boundaries and internal holes/cutouts with polygon approximation.
"""

from typing import List, Dict, Any, Tuple
import cv2
import numpy as np


class ContourDetector:
    def __init__(self, min_area_px: float = 100.0, epsilon_factor: float = 0.01):
        self.min_area_px = float(min_area_px)
        self.epsilon_factor = float(epsilon_factor)

    def extract_hierarchy(self, binary_mask: np.ndarray) -> List[Dict[str, Any]]:
        """
        Extracts 2-level contour hierarchy.
        Returns list of outer parts, each containing its inner holes and properties.
        """
        contours, hierarchy = cv2.findContours(binary_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS)
        if not contours or hierarchy is None:
            return []

        hierarchy = hierarchy[0]
        parts = []

        for i, h_info in enumerate(hierarchy):
            parent_idx = h_info[3]
            if parent_idx == -1:  # Root contour (outer solid)
                cnt = contours[i]
                area = cv2.contourArea(cnt)
                if area < self.min_area_px:
                    continue

                holes = []
                child_idx = h_info[2]
                while child_idx != -1:
                    child_cnt = contours[child_idx]
                    child_area = cv2.contourArea(child_cnt)
                    if child_area >= (self.min_area_px * 0.15):
                        holes.append(child_cnt)
                    child_idx = hierarchy[child_idx][0]  # Next child sibling

                parts.append({
                    "id": len(parts) + 1,
                    "outer_contour": cnt,
                    "holes": holes,
                    "area_px": area,
                    "bbox_px": cv2.boundingRect(cnt)
                })

        parts.sort(key=lambda p: p["area_px"], reverse=True)
        return parts

    def approximate_polygon(self, contour: np.ndarray, epsilon: float = None) -> List[Tuple[float, float]]:
        """Simplifies contour into minimal polygon vertices using Douglas-Peucker."""
        peri = cv2.arcLength(contour, True)
        if epsilon is None:
            epsilon = max(1.0, peri * self.epsilon_factor)

        approx = cv2.approxPolyDP(contour, epsilon, True)
        pts = [(float(pt[0][0]), float(pt[0][1])) for pt in approx]
        return pts
