"""
Sketch Builder
Constructs fully constrained 2D FreeCAD Sketcher sketches.
"""

from typing import List, Tuple, Dict, Any, Optional
import FreeCAD as App
import Part
import Sketcher


class SketchBuilder:
    def __init__(self, document, body, sketch_name: str = "Sketch"):
        self.doc = document
        self.body = body
        self.sketch = self.doc.addObject("Sketcher::SketchObject", sketch_name)
        self.body.addObject(self.sketch)

    def attach_to_plane(self, plane_str: str = "XY_Plane", offset_z: float = 0.0):
        """Attaches sketch to base plane or face."""
        if plane_str == "XY_Plane":
            self.sketch.Placement = App.Placement(App.Vector(0, 0, offset_z), App.Rotation(0, 0, 0, 1))
            self.sketch.MapMode = "Deactivated"
        elif plane_str == "XZ_Plane":
            # Rotate 90 deg around X
            self.sketch.Placement = App.Placement(App.Vector(0, 0, offset_z), App.Rotation(App.Vector(1, 0, 0), 90))
            self.sketch.MapMode = "Deactivated"
        elif plane_str == "YZ_Plane":
            # Rotate 90 deg around Y
            self.sketch.Placement = App.Placement(App.Vector(0, 0, offset_z), App.Rotation(App.Vector(0, 1, 0), 90))
            self.sketch.MapMode = "Deactivated"
        return self

    def add_rectangle_centered(self, width: float, height: float):
        """Adds a centered rectangular profile with Coincident & Parallel constraints."""
        hw = width / 2.0
        hh = height / 2.0

        p1 = App.Vector(-hw, -hh, 0)
        p2 = App.Vector(hw, -hh, 0)
        p3 = App.Vector(hw, hh, 0)
        p4 = App.Vector(-hw, hh, 0)

        # Lines 0, 1, 2, 3
        self.sketch.addGeometry(Part.LineSegment(p1, p2))
        self.sketch.addGeometry(Part.LineSegment(p2, p3))
        self.sketch.addGeometry(Part.LineSegment(p3, p4))
        self.sketch.addGeometry(Part.LineSegment(p4, p1))

        # Coincident corners
        self.sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 2, 1, 1))
        self.sketch.addConstraint(Sketcher.Constraint("Coincident", 1, 2, 2, 1))
        self.sketch.addConstraint(Sketcher.Constraint("Coincident", 2, 2, 3, 1))
        self.sketch.addConstraint(Sketcher.Constraint("Coincident", 3, 2, 0, 1))

        # Horizontal & Vertical
        self.sketch.addConstraint(Sketcher.Constraint("Horizontal", 0))
        self.sketch.addConstraint(Sketcher.Constraint("Vertical", 1))
        self.sketch.addConstraint(Sketcher.Constraint("Horizontal", 2))
        self.sketch.addConstraint(Sketcher.Constraint("Vertical", 3))

        # Dimensional constraints
        self.sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, width))
        self.sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, height))
        return self

    def add_polygon(self, points: List[Tuple[float, float]]):
        """Adds a closed polygon loop of line segments with Coincident constraints."""
        n = len(points)
        if n < 3:
            raise ValueError("Polygon must contain at least 3 vertices.")

        start_geom_idx = self.sketch.GeometryCount

        for i in range(n):
            j = (i + 1) % n
            p_start = App.Vector(points[i][0], points[i][1], 0)
            p_end = App.Vector(points[j][0], points[j][1], 0)
            self.sketch.addGeometry(Part.LineSegment(p_start, p_end))

        # Connect consecutive endpoints
        for i in range(n):
            g1 = start_geom_idx + i
            g2 = start_geom_idx + ((i + 1) % n)
            self.sketch.addConstraint(Sketcher.Constraint("Coincident", g1, 2, g2, 1))

        return self

    def add_circle(self, center_x: float, center_y: float, radius: float):
        """Adds a parametric circle with center position and Radius constraint."""
        c = Part.Circle(App.Vector(center_x, center_y, 0), App.Vector(0, 0, 1), radius)
        idx = self.sketch.addGeometry(c)
        self.sketch.addConstraint(Sketcher.Constraint("Radius", idx, radius))
        return idx

    def get_sketch(self):
        return self.sketch
