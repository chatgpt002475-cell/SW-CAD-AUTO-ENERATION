"""
Geometry Validation
Inspects topological and geometric health of FreeCAD solids.
"""

from typing import Dict, Any

class GeometryValidator:
    @staticmethod
    def validate_solid(body_or_shape) -> Dict[str, Any]:
        """Performs rigorous solid checks on a FreeCAD Body or TopoShape."""
        if hasattr(body_or_shape, "Shape"):
            shape = body_or_shape.Shape
        else:
            shape = body_or_shape

        report = {
            "is_valid": False,
            "is_null": True,
            "is_closed": False,
            "volume_cm3": 0.0,
            "surface_area_cm2": 0.0,
            "solids_count": 0,
            "shells_count": 0,
            "faces_count": 0,
            "edges_count": 0,
            "vertices_count": 0,
            "bounding_box_mm": None,
            "warnings": [],
            "errors": []
        }

        if shape is None or shape.isNull():
            report["errors"].append("Shape is null or undefined.")
            return report

        report["is_null"] = False
        report["is_valid"] = shape.isValid()
        report["solids_count"] = len(shape.Solids)
        report["shells_count"] = len(shape.Shells)
        report["faces_count"] = len(shape.Faces)
        report["edges_count"] = len(shape.Edges)
        report["vertices_count"] = len(shape.Vertexes)

        # Volume & Area
        try:
            vol = shape.Volume
            report["volume_cm3"] = round(vol / 1000.0, 3)
            report["surface_area_cm2"] = round(shape.Area / 100.0, 3)
        except Exception as e:
            report["warnings"].append(f"Could not compute volume/area: {e}")

        # Bounding box
        bbox = shape.BoundBox
        report["bounding_box_mm"] = {
            "x_len": round(bbox.XLength, 2),
            "y_len": round(bbox.YLength, 2),
            "z_len": round(bbox.ZLength, 2),
            "min": (round(bbox.XMin, 2), round(bbox.YMin, 2), round(bbox.ZMin, 2)),
            "max": (round(bbox.XMax, 2), round(bbox.YMax, 2), round(bbox.ZMax, 2))
        }

        # Check if closed manifold solid
        if report["solids_count"] < 1:
            report["errors"].append("Shape does not contain any valid closed solids.")
        elif report["solids_count"] > 1:
            report["warnings"].append(f"Model contains {report['solids_count']} disconnected solids.")

        if not report["is_valid"]:
            report["errors"].append("OpenCASCADE geometric kernel reported invalid topology or self-intersection.")

        if report["volume_cm3"] <= 0.0:
            report["errors"].append("Solid has zero or negative volume.")

        return report
