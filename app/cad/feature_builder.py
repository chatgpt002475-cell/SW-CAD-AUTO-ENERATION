"""
CAD Feature Builder
Constructs genuine FreeCAD PartDesign solid features:
Pads, Pockets, Holes, Flanges, Ribs, Fillets, Chamfers, and Datum Planes.
"""

from typing import List, Tuple, Optional, Any
import FreeCAD as App
import Part
import Sketcher
from .sketch_builder import SketchBuilder


class FeatureBuilder:
    def __init__(self, doc_manager, body_name: str = "Body"):
        self.dm = doc_manager
        self.doc = doc_manager.get_document()
        self.body = doc_manager.get_body(body_name)

    def create_sketch(self, name: str, plane: str = "XY_Plane", offset_z: float = 0.0) -> SketchBuilder:
        sb = SketchBuilder(self.doc, self.body, name)
        sb.attach_to_plane(plane, offset_z)
        return sb

    def add_pad(self, sketch_obj, length_mm: float, name: str = "Pad", reversed_dir: bool = False):
        """Creates an additive PartDesign::Pad."""
        pad = self.doc.addObject("PartDesign::Pad", name)
        self.body.addObject(pad)
        pad.Profile = sketch_obj
        pad.Length = float(length_mm)
        pad.Reversed = reversed_dir
        self.dm.recompute()
        return pad

    def add_pocket(self, sketch_obj, length_mm: float = 10.0, through_all: bool = False, name: str = "Pocket"):
        """Creates a subtractive PartDesign::Pocket."""
        pocket = self.doc.addObject("PartDesign::Pocket", name)
        self.body.addObject(pocket)
        pocket.Profile = sketch_obj
        if through_all:
            pocket.Type = 1  # ThroughAll in FreeCAD PartDesign
        else:
            pocket.Type = 0  # Length
            pocket.Length = float(length_mm)
        self.dm.recompute()
        return pocket

    def add_datum_plane(self, name: str = "DatumPlane", plane: str = "XY_Plane", offset: float = 0.0, angle_deg: float = 0.0):
        """Creates a parametric Datum Plane for secondary features."""
        dp = self.doc.addObject("PartDesign::Plane", name)
        self.body.addObject(dp)
        if plane == "XZ_Plane":
            dp.Placement = App.Placement(App.Vector(0, offset, 0), App.Rotation(App.Vector(1, 0, 0), 90 + angle_deg))
        elif plane == "YZ_Plane":
            dp.Placement = App.Placement(App.Vector(offset, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90 + angle_deg))
        else:
            dp.Placement = App.Placement(App.Vector(0, 0, offset), App.Rotation(App.Vector(0, 0, 1), angle_deg))
        dp.MapMode = "Deactivated"
        self.dm.recompute()
        return dp

    def add_hole_subtraction(
        self,
        center_x: float,
        center_y: float,
        diameter_mm: float,
        depth_mm: Optional[float] = None,
        through_all: bool = True,
        sketch_name: str = "HoleSketch",
        feature_name: str = "HoleCutout"
    ):
        """Constructs a circular cutout (through hole or blind hole)."""
        sb = self.create_sketch(sketch_name, "XY_Plane")
        sb.add_circle(center_x, center_y, diameter_mm / 2.0)
        self.dm.recompute()
        return self.add_pocket(sb.get_sketch(), length_mm=depth_mm or 100.0, through_all=through_all, name=feature_name)

    def add_counterbore_hole(
        self,
        center_x: float,
        center_y: float,
        bore_dia_mm: float,
        counterbore_dia_mm: float,
        counterbore_depth_mm: float,
        through_all: bool = True
    ):
        """Constructs a counterbored stepped hole."""
        # 1. Main through hole
        h1 = self.add_hole_subtraction(center_x, center_y, bore_dia_mm, through_all=through_all, sketch_name=f"BoreSketch_{center_x}_{center_y}")
        # 2. Counterbore step
        sb2 = self.create_sketch(f"CboreSketch_{center_x}_{center_y}", "XY_Plane")
        sb2.add_circle(center_x, center_y, counterbore_dia_mm / 2.0)
        self.dm.recompute()
        h2 = self.add_pocket(sb2.get_sketch(), length_mm=counterbore_depth_mm, through_all=False, name=f"CborePocket_{center_x}_{center_y}")
        return h1, h2

    def add_fillet(self, radius_mm: float, name: str = "Fillet"):
        """Adds fillets to top horizontal edges."""
        if not hasattr(self.body, "Shape") or self.body.Shape.isNull():
            return None
        edges = []
        for i, edge in enumerate(self.body.Shape.Edges):
            # Pick horizontal edges
            if abs(edge.Vertexes[0].Point.z - edge.Vertexes[-1].Point.z) < 1e-4:
                edges.append(f"Edge{i+1}")
                if len(edges) >= 4:
                    break

        if not edges:
            return None

        fillet = self.doc.addObject("PartDesign::Fillet", name)
        self.body.addObject(fillet)
        fillet.Base = (self.body.Tip, edges)
        fillet.Radius = float(radius_mm)
        self.dm.recompute()
        return fillet
