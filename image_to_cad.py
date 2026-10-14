"""
Image to 3D CAD Converter (STEP / B-Rep)
Engine: OpenCV (Image Processing & Vector Tracing) + build123d / Open CASCADE (Geometric Kernel)

Converts 2D engineering drawings, blueprints, sketches, and silhouette images
into true ISO 10303 STEP B-Rep CAD solids.
"""

import os
import sys
import math
import argparse
from typing import List, Tuple, Dict, Any, Optional

import cv2
import numpy as np
from PIL import Image

try:
    from build123d import (
        BuildPart, BuildSketch, Locations,
        Plane, Axis, Mode,
        Polygon, Circle, make_face,
        extrude, revolve, fillet, chamfer,
        export_step, export_stl,
        Compound, Solid, Face, Wire, Edge, Vector
    )
except ImportError as e:
    raise ImportError(f"Required CAD kernel library not found: {e}")


class ImageToCadConverter:
    def __init__(
        self,
        thickness_mm: float = 10.0,
        target_width_mm: float = 100.0,
        epsilon: float = 1.5,
        detect_circles: bool = True,
        circularity_threshold: float = 0.88,
        invert: Optional[bool] = None,
        min_contour_area_px: float = 100.0
    ):
        """
        :param thickness_mm: Extrusion thickness in millimeters.
        :param target_width_mm: Physical real-world width of the part in millimeters.
        :param epsilon: Polygon simplification tolerance (Douglas-Peucker).
        :param detect_circles: Whether to fit exact analytic circles for round holes/bosses.
        :param circularity_threshold: Circularity threshold (0.0 to 1.0) to qualify as circle.
        :param invert: Force invert binary mask (None = auto-detect background).
        :param min_contour_area_px: Minimum contour area in pixels to ignore speckles/noise.
        """
        self.thickness_mm = float(thickness_mm)
        self.target_width_mm = float(target_width_mm)
        self.epsilon = float(epsilon)
        self.detect_circles = detect_circles
        self.circularity_threshold = float(circularity_threshold)
        self.invert = invert
        self.min_contour_area_px = float(min_contour_area_px)

    def load_and_preprocess(self, image_path: str) -> Tuple[np.ndarray, float]:
        """Loads image, handles transparency, normalizes polarity, returns binary mask."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file does not exist: {image_path}")

        pil_img = Image.open(image_path)
        
        # Handle alpha channel (composite over white background)
        if pil_img.mode in ('RGBA', 'LA') or (pil_img.mode == 'P' and 'transparency' in pil_img.info):
            bg = Image.new('RGB', pil_img.size, (255, 255, 255))
            if pil_img.mode != 'RGBA':
                pil_img = pil_img.convert('RGBA')
            bg.paste(pil_img, mask=pil_img.split()[-1])
            img_rgb = np.array(bg)
        else:
            img_rgb = np.array(pil_img.convert('RGB'))

        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

        # Bilateral filter to smooth texture while keeping sharp engineering edges
        smoothed = cv2.bilateralFilter(gray, d=7, sigmaColor=75, sigmaSpace=75)

        # Otsu thresholding
        _, thresh = cv2.threshold(smoothed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Determine polarity: Mechanical drawings are typically black lines on white paper.
        # Contours require foreground (part solid) to be WHITE (255) and background BLACK (0).
        h, w = thresh.shape
        border_pixels = np.concatenate([
            thresh[0, :], thresh[-1, :],
            thresh[:, 0], thresh[:, -1]
        ])
        border_white_ratio = np.mean(border_pixels == 255)

        if self.invert is not None:
            if self.invert:
                mask = cv2.bitwise_not(thresh)
            else:
                mask = thresh
        else:
            # Auto-detect: if border is mostly white, invert so part interior is white
            if border_white_ratio > 0.5:
                mask = cv2.bitwise_not(thresh)
            else:
                mask = thresh

        # Morphological close to bridge tiny anti-aliasing gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        return mask, float(w)

    def extract_contours_and_hierarchy(self, mask: np.ndarray) -> List[Dict[str, Any]]:
        """
        Extracts 2-level contour hierarchy:
        Outer parts (solids) and their internal holes (voids).
        """
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS)

        if not contours or hierarchy is None:
            raise ValueError("No distinct geometry contours found in image.")

        hierarchy = hierarchy[0]  # Shape: (N, 4) -> [Next, Previous, First_Child, Parent]
        parts = []

        # Find all root-level contours (Parent == -1)
        for i, h_info in enumerate(hierarchy):
            parent_idx = h_info[3]
            if parent_idx == -1:
                outer_cnt = contours[i]
                area = cv2.contourArea(outer_cnt)
                if area < self.min_contour_area_px:
                    continue

                holes = []
                child_idx = h_info[2]
                while child_idx != -1:
                    child_cnt = contours[child_idx]
                    child_area = cv2.contourArea(child_cnt)
                    if child_area >= (self.min_contour_area_px * 0.2):
                        holes.append(child_cnt)
                    child_idx = hierarchy[child_idx][0]  # Next sibling

                parts.append({
                    "outer": outer_cnt,
                    "holes": holes,
                    "area": area
                })

        # Sort parts by area descending
        parts.sort(key=lambda p: p["area"], reverse=True)
        return parts

    def _contour_to_points(
        self,
        cnt: np.ndarray,
        scale: float,
        img_center_x: float,
        img_center_y: float
    ) -> Tuple[List[Tuple[float, float]], Optional[Dict[str, float]]]:
        """
        Simplifies contour and converts pixel coordinates to centered mm coordinates.
        Also tests if contour is a true circle/arc.
        """
        area = cv2.contourArea(cnt)
        perimeter = cv2.arcLength(cnt, True)
        circle_fit = None

        if perimeter > 0 and self.detect_circles:
            circularity = (4.0 * math.pi * area) / (perimeter * perimeter)
            if circularity >= self.circularity_threshold:
                (cx, cy), radius = cv2.minEnclosingCircle(cnt)
                if radius > 1.5:  # Ignore subpixel noise
                    circle_fit = {
                        "x": (cx - img_center_x) * scale,
                        "y": -(cy - img_center_y) * scale,  # Invert Y for standard CAD coordinates
                        "radius": radius * scale
                    }

        # Douglas-Peucker simplification
        epsilon_px = max(0.5, self.epsilon / scale)
        approx = cv2.approxPolyDP(cnt, epsilon_px, True)
        
        # Ensure at least 3 points
        pts = []
        for pt in approx:
            px, py = pt[0]
            x_mm = (px - img_center_x) * scale
            y_mm = -(py - img_center_y) * scale
            pts.append((float(x_mm), float(y_mm)))

        # Remove duplicate consecutive points
        clean_pts = []
        for p in pts:
            if not clean_pts or (math.hypot(p[0] - clean_pts[-1][0], p[1] - clean_pts[-1][1]) > 0.05):
                clean_pts.append(p)

        if len(clean_pts) > 2:
            # Ensure not identical start/end in list
            if math.hypot(clean_pts[0][0] - clean_pts[-1][0], clean_pts[0][1] - clean_pts[-1][1]) < 0.05:
                clean_pts.pop()

        return clean_pts, circle_fit

    def generate_solid(self, image_path: str, mode: str = "extrude") -> Compound:
        """
        Generates 3D CAD B-Rep solid from image.
        :param mode: 'extrude' (Prismatic plate/solid) or 'revolve' (Rotational solid).
        """
        mask, img_w = self.load_and_preprocess(image_path)
        img_h = mask.shape[0]

        parts_data = self.extract_contours_and_hierarchy(mask)
        if not parts_data:
            raise ValueError("No valid parts detected in image contour hierarchy.")

        # Find total bounding box of all outer parts to compute exact scale to target_width_mm
        all_pts = np.vstack([p["outer"] for p in parts_data])
        min_x, min_y, bbox_w, bbox_h = cv2.boundingRect(all_pts)
        
        scale = self.target_width_mm / max(1.0, float(bbox_w))
        center_x = min_x + bbox_w / 2.0
        center_y = min_y + bbox_h / 2.0

        solids: List[Solid] = []

        if mode == "extrude":
            for part_idx, part in enumerate(parts_data):
                outer_pts, outer_circle = self._contour_to_points(part["outer"], scale, center_x, center_y)
                
                with BuildPart() as bp:
                    with BuildSketch(Plane.XY) as bs:
                        if outer_circle is not None and len(outer_pts) < 12:
                            # Exact analytical circle
                            with Locations((outer_circle["x"], outer_circle["y"])):
                                Circle(radius=outer_circle["radius"], mode=Mode.ADD)
                        else:
                            if len(outer_pts) >= 3:
                                Polygon(outer_pts, mode=Mode.ADD)

                        # Cut internal holes
                        for hole_cnt in part["holes"]:
                            hole_pts, hole_circle = self._contour_to_points(hole_cnt, scale, center_x, center_y)
                            if hole_circle is not None:
                                # Exact analytical circle hole
                                with Locations((hole_circle["x"], hole_circle["y"])):
                                    Circle(radius=hole_circle["radius"], mode=Mode.SUBTRACT)
                            elif len(hole_pts) >= 3:
                                Polygon(hole_pts, mode=Mode.SUBTRACT)

                    if bs.sketch and bs.sketch.faces():
                        extrude(amount=self.thickness_mm)
                        if bp.part:
                            solids.append(bp.part)

        elif mode == "revolve":
            # Revolve primary contour around Z axis
            primary_part = parts_data[0]
            outer_pts, _ = self._contour_to_points(primary_part["outer"], scale, center_x, center_y)
            
            # For lathe/revolve, profile must be on one side of revolution axis (X >= 0)
            xs = [p[0] for p in outer_pts]
            min_px = min(xs)
            shifted_pts = [(p[0] - min_px, p[1]) for p in outer_pts]

            with BuildPart() as bp:
                with BuildSketch(Plane.XZ) as bs:
                    if len(shifted_pts) >= 3:
                        Polygon(shifted_pts, mode=Mode.ADD)
                if bs.sketch and bs.sketch.faces():
                    revolve(axis=Axis.Z, revolution_arc=360)
                    if bp.part:
                        solids.append(bp.part)

        else:
            raise ValueError(f"Unsupported CAD mode: '{mode}'. Choose 'extrude' or 'revolve'.")

        if not solids:
            raise RuntimeError("Failed to generate valid 3D CAD solid from contours.")

        if len(solids) == 1:
            return solids[0]
        return Compound(solids)

    def convert(
        self,
        image_path: str,
        output_step_path: str,
        mode: str = "extrude",
        export_stl_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes full pipeline and writes ISO 10303 STEP file.
        """
        cad_model = self.generate_solid(image_path, mode=mode)
        
        # Ensure output directory exists
        out_dir = os.path.dirname(os.path.abspath(output_step_path))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Export STEP
        export_step(cad_model, output_step_path)
        file_size = os.path.getsize(output_step_path)

        result = {
            "status": "success",
            "step_path": output_step_path,
            "step_size_bytes": file_size,
            "mode": mode,
            "thickness_mm": self.thickness_mm,
            "target_width_mm": self.target_width_mm,
            "volume_cm3": float(cad_model.volume / 1000.0) if hasattr(cad_model, "volume") else 0.0
        }

        if export_stl_path:
            stl_dir = os.path.dirname(os.path.abspath(export_stl_path))
            if stl_dir and not os.path.exists(stl_dir):
                os.makedirs(stl_dir, exist_ok=True)
            export_stl(cad_model, export_stl_path)
            result["stl_path"] = export_stl_path

        return result


def main():
    parser = argparse.ArgumentParser(
        description="Convert 2D Image / Blueprint / Sketch into ISO 10303 3D CAD STEP Solid."
    )
    parser.add_argument("input_image", help="Path to input 2D image (PNG, JPG, BMP, etc.)")
    parser.add_argument("-o", "--output", default="output.step", help="Output STEP file path (default: output.step)")
    parser.add_argument("-t", "--thickness", type=float, default=10.0, help="Extrusion thickness in mm (default: 10.0)")
    parser.add_argument("-w", "--width", type=float, default=100.0, help="Target physical width in mm (default: 100.0)")
    parser.add_argument("-m", "--mode", choices=["extrude", "revolve"], default="extrude", help="CAD engine mode")
    parser.add_argument("--epsilon", type=float, default=1.5, help="Vector simplification tolerance (default: 1.5)")
    parser.add_argument("--stl", help="Optional output STL mesh file path")
    parser.add_argument("--invert", action="store_true", help="Force invert black/white polarity")

    args = parser.parse_args()

    converter = ImageToCadConverter(
        thickness_mm=args.thickness,
        target_width_mm=args.width,
        epsilon=args.epsilon,
        invert=True if args.invert else None
    )

    print(f"[*] Processing image: {args.input_image}")
    print(f"[*] Generating {args.mode.upper()} 3D CAD solid...")
    res = converter.convert(
        image_path=args.input_image,
        output_step_path=args.output,
        mode=args.mode,
        export_stl_path=args.stl
    )

    print(f"[+] STEP Solid generated successfully!")
    print(f"    File: {res['step_path']} ({res['step_size_bytes']} bytes)")
    print(f"    Volume: {res['volume_cm3']:.2f} cm³")
    if "stl_path" in res:
        print(f"    STL:  {res['stl_path']}")


if __name__ == "__main__":
    main()
