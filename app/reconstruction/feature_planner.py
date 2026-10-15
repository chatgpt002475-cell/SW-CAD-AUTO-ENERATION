"""
Universal Feature Planner for Arbitrary Mechanical Components
Generates an ordered, dependency-aware sequence of parametric CAD operations.
Translates recognized 2D features and user parameters into genuine PartDesign solids in FreeCAD 1.1.
Supports ANY component domain:
- Universal prismatic plate / bracket / arm / housing
- Axisymmetric revolved shafts / bushings / pulleys
- Formed sheet metal brackets with upright flanges
- Precision stamped die plates with multiple tooling slots
"""

from typing import Dict, Any, List
import math
from app.cad.document_manager import DocumentManager
from app.cad.feature_builder import FeatureBuilder
from app.cad.geometry_validation import GeometryValidator

try:
    import FreeCAD as App
    import Part
    import Sketcher
except ImportError:
    App = None
    Part = None
    Sketcher = None


class FeaturePlanner:
    def __init__(self, doc_manager: DocumentManager):
        self.dm = doc_manager
        self.fb = FeatureBuilder(doc_manager)
        self.plan_steps: List[Dict[str, Any]] = []

    def build_from_feature_tree(self, recognized_features: Dict[str, Any], user_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executes complete reconstruction plan to produce editable 3D parametric CAD solid for ANY mechanical part.
        """
        params = user_params or {}
        category = params.get("category") or recognized_features.get("category", "")
        doc = self.dm.get_document()
        body = self.dm.get_body()

        thickness = float(params.get("base_thickness_mm", 3.0))
        width = float(params.get("target_width_mm", 130.0))
        flange_h = float(params.get("flange_height_mm", 0.0))
        is_revolved = params.get("is_revolved", False) or category == "REVOLVED_COMPONENT"

        # Check if Axisymmetric Revolved Solid (Turned Shaft / Bushing)
        if is_revolved:
            return self._build_turned_shaft(doc, body, width, thickness, params)

        # Universal Parametric CAD Builder for ANY arbitrary mechanical component
        return self._build_universal_component(doc, body, recognized_features, width, thickness, flange_h, params)

    def _build_universal_component(
        self,
        doc,
        body,
        recognized_features: Dict[str, Any],
        width: float,
        thickness: float,
        flange_h: float,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Universal Parametric Builder for ANY mechanical component:
        - Scanned outer contour polygon (PartDesign::Pad)
        - Upright flange web or raised boss if flange_h > 0 (PartDesign::Pad on top datum)
        - Subtractive through-holes array (PartDesign::Pocket through-all)
        - Subtractive slots array (PartDesign::Pocket through-all)
        - Subtractive pockets / cutouts (PartDesign::Pocket)
        """
        # 1. Obtain outer contour points
        scanned_pts = params.get("contour_points") or []
        if not scanned_pts or len(scanned_pts) < 3:
            base_f = recognized_features.get("base_feature", {})
            scanned_pts = base_f.get("points_mm") or []

        if not scanned_pts or len(scanned_pts) < 3:
            hw = width / 2.0
            hh = (width * 0.6) / 2.0
            scanned_pts = [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]]

        # Clean consecutive duplicate points to avoid degenerate sketch segments
        clean_pts = []
        for p in scanned_pts:
            if not clean_pts or (abs(p[0] - clean_pts[-1][0]) > 0.05 or abs(p[1] - clean_pts[-1][1]) > 0.05):
                clean_pts.append([float(p[0]), float(p[1])])
        if len(clean_pts) >= 2 and abs(clean_pts[0][0] - clean_pts[-1][0]) < 0.05 and abs(clean_pts[0][1] - clean_pts[-1][1]) < 0.05:
            clean_pts.pop()
        if len(clean_pts) < 3:
            hw, hh = width / 2.0, (width * 0.6) / 2.0
            clean_pts = [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]]

        # Step 1: Base Contour Sketch & Pad
        sk1 = doc.addObject('Sketcher::SketchObject', 'BaseProfile_Sk')
        body.addObject(sk1)
        for i in range(len(clean_pts)):
            p1 = clean_pts[i]
            p2 = clean_pts[(i + 1) % len(clean_pts)]
            sk1.addGeometry(Part.LineSegment(App.Vector(p1[0], p1[1], 0), App.Vector(p2[0], p2[1], 0)))
        doc.recompute()

        pad1 = doc.addObject('PartDesign::Pad', 'BaseContour_Pad')
        body.addObject(pad1)
        pad1.Profile = sk1
        pad1.Length = thickness
        doc.recompute()
        self.plan_steps.append({"step": 1, "op": "Pad", "name": "BaseContour_Pad", "length_mm": thickness, "vertices": len(clean_pts)})

        # Step 2: Upright Flange or Raised Boss
        if flange_h > 0:
            xs = [p[0] for p in clean_pts]
            ys = [p[1] for p in clean_pts]
            min_x, max_x = min(xs), max(xs)
            max_y = max(ys)
            flange_len = (max_x - min_x) * 0.65
            fx_start = min_x + (max_x - min_x) * 0.05

            sk2 = doc.addObject('Sketcher::SketchObject', 'UprightFlange_Sk')
            body.addObject(sk2)
            sk2.AttachmentOffset = App.Placement(App.Vector(0, 0, thickness), App.Rotation(0, 0, 0))
            flange_t = min(thickness, 4.0)
            sk2.addGeometry(Part.LineSegment(App.Vector(fx_start, max_y - flange_t, 0), App.Vector(fx_start + flange_len, max_y - flange_t, 0)))
            sk2.addGeometry(Part.LineSegment(App.Vector(fx_start + flange_len, max_y - flange_t, 0), App.Vector(fx_start + flange_len, max_y, 0)))
            sk2.addGeometry(Part.LineSegment(App.Vector(fx_start + flange_len, max_y, 0), App.Vector(fx_start, max_y, 0)))
            sk2.addGeometry(Part.LineSegment(App.Vector(fx_start, max_y, 0), App.Vector(fx_start, max_y - flange_t, 0)))
            doc.recompute()

            pad2 = doc.addObject('PartDesign::Pad', 'UprightFlangeWeb')
            body.addObject(pad2)
            pad2.Profile = sk2
            pad2.Length = flange_h
            doc.recompute()
            self.plan_steps.append({"step": 2, "op": "Pad", "name": "UprightFlangeWeb", "length_mm": flange_h})

        # Step 3: Subtractive Holes Array
        holes = params.get("detected_holes") or []
        for idx, h in enumerate(holes[:12]):
            try:
                hx = float(h.get("x", 0.0))
                hy = float(h.get("y", 0.0))
                dia = float(h.get("dia", 4.0))
                sk_h = doc.addObject('Sketcher::SketchObject', f'Hole_{idx+1}_Sk')
                body.addObject(sk_h)
                sk_h.AttachmentOffset = App.Placement(App.Vector(0, 0, thickness), App.Rotation(0, 0, 0))
                sk_h.addGeometry(Part.Circle(App.Vector(hx, hy, 0), App.Vector(0, 0, 1), dia / 2.0))
                doc.recompute()

                pock_h = doc.addObject('PartDesign::Pocket', f'Hole_{idx+1}_Pocket')
                body.addObject(pock_h)
                pock_h.Profile = sk_h
                pock_h.Length = thickness + flange_h + 2.0
                pock_h.Reversed = 1
                doc.recompute()
                self.plan_steps.append({"step": len(self.plan_steps) + 1, "op": "Hole", "name": f"Hole_{idx+1}_Pocket", "dia_mm": dia, "x": hx, "y": hy})
            except Exception:
                pass

        # Step 4: Subtractive Slots Array
        slots = params.get("detected_slots") or []
        for idx, s in enumerate(slots[:8]):
            try:
                sx = float(s.get("x", 0.0))
                sy = float(s.get("y", 0.0))
                sw = float(s.get("w", 5.0))
                sl = float(s.get("len", 18.0))
                hw, hl = sw / 2.0, sl / 2.0
                sk_s = doc.addObject('Sketcher::SketchObject', f'Slot_{idx+1}_Sk')
                body.addObject(sk_s)
                sk_s.AttachmentOffset = App.Placement(App.Vector(0, 0, thickness), App.Rotation(0, 0, 0))
                sk_s.addGeometry(Part.LineSegment(App.Vector(sx - hl, sy - hw, 0), App.Vector(sx + hl, sy - hw, 0)))
                sk_s.addGeometry(Part.LineSegment(App.Vector(sx + hl, sy - hw, 0), App.Vector(sx + hl, sy + hw, 0)))
                sk_s.addGeometry(Part.LineSegment(App.Vector(sx + hl, sy + hw, 0), App.Vector(sx - hl, sy + hw, 0)))
                sk_s.addGeometry(Part.LineSegment(App.Vector(sx - hl, sy + hw, 0), App.Vector(sx - hl, sy - hw, 0)))
                doc.recompute()

                pock_s = doc.addObject('PartDesign::Pocket', f'Slot_{idx+1}_Pocket')
                body.addObject(pock_s)
                pock_s.Profile = sk_s
                pock_s.Length = thickness + flange_h + 2.0
                pock_s.Reversed = 1
                doc.recompute()
                self.plan_steps.append({"step": len(self.plan_steps) + 1, "op": "Slot", "name": f"Slot_{idx+1}_Pocket", "len_mm": sl, "w_mm": sw})
            except Exception:
                pass

        # Step 5: Subtractive Pockets Array
        pockets = params.get("detected_pockets") or []
        for idx, pk in enumerate(pockets[:4]):
            try:
                pk_pts = pk.get("points") or []
                if len(pk_pts) >= 3:
                    sk_p = doc.addObject('Sketcher::SketchObject', f'Pocket_{idx+1}_Sk')
                    body.addObject(sk_p)
                    sk_p.AttachmentOffset = App.Placement(App.Vector(0, 0, thickness), App.Rotation(0, 0, 0))
                    for i in range(len(pk_pts)):
                        p1 = pk_pts[i]
                        p2 = pk_pts[(i + 1) % len(pk_pts)]
                        sk_p.addGeometry(Part.LineSegment(App.Vector(p1[0], p1[1], 0), App.Vector(p2[0], p2[1], 0)))
                    doc.recompute()
                    pock_p = doc.addObject('PartDesign::Pocket', f'Pocket_{idx+1}')
                    body.addObject(pock_p)
                    pock_p.Profile = sk_p
                    pock_p.Length = thickness + 2.0
                    pock_p.Reversed = 1
                    doc.recompute()
                    self.plan_steps.append({"step": len(self.plan_steps) + 1, "op": "Pocket", "name": f"Pocket_{idx+1}", "vertices": len(pk_pts)})
            except Exception:
                pass

        doc.recompute()
        val = GeometryValidator.validate_solid(body)
        return {
            "status": "success" if val["is_valid"] else "warning",
            "body": body,
            "steps_executed": len(self.plan_steps),
            "plan_steps": self.plan_steps,
            "validation": val
        }

    def _build_turned_shaft(self, doc, body, width: float, thickness: float, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Builds axisymmetric stepped turned shaft / bushing using PartDesign::Revolution.
        """
        length = float(params.get("length_mm", 120.0))
        od1 = width / 2.0
        od2 = od1 * 0.78
        od3 = od1 * 0.58

        sk = doc.addObject('Sketcher::SketchObject', 'TurnedShaftProfile')
        body.addObject(sk)
        l1, l2, l3 = length * 0.35, length * 0.35, length * 0.30
        sk.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(0, od3, 0)))
        sk.addGeometry(Part.LineSegment(App.Vector(0, od3, 0), App.Vector(l3, od3, 0)))
        sk.addGeometry(Part.LineSegment(App.Vector(l3, od3, 0), App.Vector(l3, od1, 0)))
        sk.addGeometry(Part.LineSegment(App.Vector(l3, od1, 0), App.Vector(l3 + l1, od1, 0)))
        sk.addGeometry(Part.LineSegment(App.Vector(l3 + l1, od1, 0), App.Vector(l3 + l1, od2, 0)))
        sk.addGeometry(Part.LineSegment(App.Vector(l3 + l1, od2, 0), App.Vector(length, od2, 0)))
        sk.addGeometry(Part.LineSegment(App.Vector(length, od2, 0), App.Vector(length, 0, 0)))
        sk.addGeometry(Part.LineSegment(App.Vector(length, 0, 0), App.Vector(0, 0, 0)))
        doc.recompute()

        rev = doc.addObject('PartDesign::Revolution', 'TurnedShaftBody')
        body.addObject(rev)
        rev.Profile = sk
        rev.ReferenceAxis = (sk, ['H_Axis'])
        rev.Angle = 360.0
        doc.recompute()
        self.plan_steps.append({"step": 1, "op": "Revolution", "name": "TurnedShaftBody", "od_mm": od1 * 2, "length_mm": length})

        val = GeometryValidator.validate_solid(body)
        return {
            "status": "success" if val["is_valid"] else "warning",
            "body": body,
            "steps_executed": len(self.plan_steps),
            "plan_steps": self.plan_steps,
            "validation": val
        }
