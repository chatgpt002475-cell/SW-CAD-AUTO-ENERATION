"""
Feature Planner
Generates an ordered, dependency-aware sequence of parametric CAD operations.
Translates recognized 2D features and user parameters into genuine PartDesign solids.
"""

from typing import Dict, Any, List
from app.cad.document_manager import DocumentManager
from app.cad.feature_builder import FeatureBuilder
from app.cad.geometry_validation import GeometryValidator


class FeaturePlanner:
    def __init__(self, doc_manager: DocumentManager):
        self.dm = doc_manager
        self.fb = FeatureBuilder(doc_manager)
        self.plan_steps: List[Dict[str, Any]] = []

    def build_from_feature_tree(self, recognized_features: Dict[str, Any], user_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executes complete reconstruction plan to produce editable 3D parametric CAD solid.
        """
        params = user_params or {}
        base_feat = recognized_features.get("base_feature", {})
        holes = recognized_features.get("holes", [])
        pockets = recognized_features.get("pockets", [])
        flanges = recognized_features.get("flanges", [])

        thickness = float(params.get("base_thickness_mm", base_feat.get("thickness_mm", 12.0)))
        body = self.dm.get_body()

        # Step 1: Base Plate Solid
        sb_base = self.fb.create_sketch("BaseSketch", "XY_Plane")
        pts = base_feat.get("points_mm", [])
        if len(pts) >= 3:
            sb_base.add_polygon(pts)
        else:
            # Fallback default block
            sb_base.add_rectangle_centered(100.0, 80.0)

        base_pad = self.fb.add_pad(sb_base.get_sketch(), length_mm=thickness, name="BasePad")
        self.plan_steps.append({"step": 1, "op": "Pad", "name": "BasePad", "length_mm": thickness})

        # Step 2: Upright Flange (if present in features or parameters)
        flange_height = float(params.get("flange_height_mm", 0.0))
        flange_thick = float(params.get("flange_thickness_mm", 10.0))
        if flange_height > 0.0:
            sb_flange = self.fb.create_sketch("FlangeSketch", "XY_Plane", offset_z=thickness)
            # Upright tab along back
            flange_w = float(params.get("flange_width_mm", 80.0))
            hw = flange_w / 2.0
            sb_flange.add_polygon([(-hw, 10.0), (hw, 10.0), (hw, 10.0 + flange_thick), (-hw, 10.0 + flange_thick)])
            self.fb.add_pad(sb_flange.get_sketch(), length_mm=flange_height, name="FlangePad")
            self.plan_steps.append({"step": 2, "op": "Pad", "name": "FlangePad", "length_mm": flange_height})

        # Step 3: Through-Holes
        for i, h in enumerate(holes):
            h_id = h.get("id", f"Hole_{i+1}")
            cx = float(h.get("center_x_mm", 0.0))
            cy = float(h.get("center_y_mm", 0.0))
            dia = float(params.get(f"{h_id}_diameter_mm", h.get("diameter_mm", 10.0)))
            through = bool(h.get("through_all", True))
            depth = float(h.get("depth_mm", thickness))

            self.fb.add_hole_subtraction(
                center_x=cx,
                center_y=cy,
                diameter_mm=dia,
                depth_mm=depth,
                through_all=through,
                sketch_name=f"{h_id}_Sketch",
                feature_name=f"{h_id}_Pocket"
            )
            self.plan_steps.append({"step": len(self.plan_steps) + 1, "op": "Pocket", "name": f"{h_id}_Pocket", "dia_mm": dia})

        # Step 4: Recessed Pockets & Slots
        for j, p in enumerate(pockets):
            p_id = p.get("id", f"Pocket_{j+1}")
            p_pts = p.get("points_mm", [])
            p_depth = float(params.get(f"{p_id}_depth_mm", p.get("depth_mm", thickness / 2.0)))
            p_through = bool(p.get("through_all", False))

            if len(p_pts) >= 3:
                sb_p = self.fb.create_sketch(f"{p_id}_Sketch", "XY_Plane", offset_z=thickness)
                sb_p.add_polygon(p_pts)
                self.fb.add_pocket(sb_p.get_sketch(), length_mm=p_depth, through_all=p_through, name=p_id)
                self.plan_steps.append({"step": len(self.plan_steps) + 1, "op": "Pocket", "name": p_id, "depth_mm": p_depth})

        # Step 5: Edge Fillets (if specified)
        fillet_radius = float(params.get("fillet_radius_mm", 0.0))
        if fillet_radius > 0.0:
            self.fb.add_fillet(radius_mm=fillet_radius, name="EdgeFillet")
            self.plan_steps.append({"step": len(self.plan_steps) + 1, "op": "Fillet", "name": "EdgeFillet", "radius_mm": fillet_radius})

        # Recompute & Validate Solid
        self.dm.recompute()
        val = GeometryValidator.validate_solid(body)

        return {
            "status": "success" if val["is_valid"] else "warning",
            "body": body,
            "steps_executed": len(self.plan_steps),
            "plan_steps": self.plan_steps,
            "validation": val
        }
